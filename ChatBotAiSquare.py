import math
import re
import unicodedata
from difflib import get_close_matches


def _sqrt(x):
    """Căn bậc hai an toàn: số âm -> báo lỗi (luật đó sẽ bị bỏ qua)"""
    if x < -1e-9:
        raise ValueError("căn của số âm")
    return math.sqrt(max(x, 0.0))

# dinh nghia 1 luat gom
# du kien can, ket qua, ky hieu toan hoc cua ket qua, giai thich, cong thuc , ky hieu cong thuc
def R(need, give, sym, expl, fn, expr):
    """Một luật: biết `need` (list) -> tính `give`"""
    return dict(need=need, give=give, sym=sym, expl=expl, fn=fn, expr=expr)


class ShapeExpertChatbot:
    NUM = r"([-+]?\d*\.\d+|\d+)"

    SHAPES = {
        "vuong":    dict(name="hình vuông",
                         attrs=["canh", "chu_vi", "dien_tich", "duong_cheo"]),
        "chu_nhat": dict(name="hình chữ nhật",
                         attrs=["dai", "rong", "nua_chu_vi", "chu_vi",
                                "dien_tich", "duong_cheo"]),
    }

    LABEL = {
        "canh": "cạnh", "dai": "chiều dài", "rong": "chiều rộng",
        "chu_vi": "chu vi", "nua_chu_vi": "nửa chu vi",
        "dien_tich": "diện tích", "duong_cheo": "đường chéo",
    }

    # ---- Từ điển biến thể (đã bỏ dấu, viết thường) ----
    ALIASES = {
        "nua_chu_vi": ["nua chu vi", "nua cv"],
        "chu_vi":     ["chu vi", "chuvi", "chu v", "chu vy", "cv"],
        "dien_tich":  ["dien tich", "dientich", "dien tic", "dt"],
        "duong_cheo": ["do dai duong cheo", "duong cheo", "duongcheo", "cheo"],
        "canh":       ["do dai canh", "canh dai", "canh", "cnh","c"],
        "dai":        ["chieu dai", "dai", "d"],
        "rong":       ["chieu rong", "rong", "r"],
    }
    #Xac dinh hinh can giai 
    SHAPE_ALIASES = {
        "shape_cn": ["hinh chu nhat", "chu nhat", "chunhat", "hcn"],
        "shape_hv": ["hinh vuong", "vuong", "hv"],
    }
    # Ký hiệu 1 chữ cái, chỉ nhận dạng "a = 5". a, b phụ thuộc loại hình nên để sau
    SYMBOLS = {"p": "chu_vi", "s": "dien_tich", "d": "duong_cheo",
               "a": "sym_a", "b": "sym_b"}

    # ---- Hệ luật ----
    RULES = {
        "vuong": [
            R(["canh"], "chu_vi", "P", "P = 4 * a với a là cạnh",
              lambda a: 4 * a, lambda a: f"4 * {a}"),
            R(["canh"], "dien_tich", "S", "S = a * a với a là cạnh",
              lambda a: a * a, lambda a: f"{a} * {a}"),
            R(["canh"], "duong_cheo", "d", "d = a * √2 với a là cạnh",
              lambda a: a * math.sqrt(2), lambda a: f"{a} * √2"),
            R(["chu_vi"], "canh", "a", "a = P / 4 với P là chu vi",
              lambda p: p / 4, lambda p: f"{p} / 4"),
            R(["duong_cheo"], "canh", "a", "a = d / √2 với d là đường chéo",
              lambda d: d / math.sqrt(2), lambda d: f"{d} / √2"),
            R(["dien_tich"], "canh", "a", "a = √S với S là diện tích",
              lambda s: _sqrt(s), lambda s: f"√{s}"),
            R(["duong_cheo"], "dien_tich", "S", "S = d * d / 2 với d là đường chéo",
              lambda d: d * d / 2, lambda d: f"{d} * {d} / 2"),
        ],
        "chu_nhat": [
            # --- Luật kiểm tra "hình chữ nhật này có phải hình vuông không" ---
            # Hình chữ nhật là hình vuông <=> a = b
            R(["dai", "rong"], "la_vuong", "kết luận",
              "hình chữ nhật là hình vuông khi chiều dài = chiều rộng (a = b)",
              lambda a, b: float(abs(a - b) < 1e-9),
              lambda a, b: f"{a} = {b}?"),

            # Biết nửa chu vi p và diện tích S: (a - b)² = p² - 4S, vuông khi p² = 4S
            R(["nua_chu_vi", "dien_tich"], "la_vuong", "kết luận",
              "hình chữ nhật là hình vuông khi p * p = 4 * S "
              "với p là nửa chu vi, S là diện tích",
              lambda p, s: float(abs(p * p - 4 * s) < 1e-9),
              lambda p, s: f"{p} * {p} = 4 * {s}?"),

            # Biết đường chéo d và diện tích S: (a - b)² = d² - 2S, vuông khi d² = 2S
            R(["duong_cheo", "dien_tich"], "la_vuong", "kết luận",
              "hình chữ nhật là hình vuông khi d * d = 2 * S "
              "với d là đường chéo, S là diện tích",
              lambda d, s: float(abs(d * d - 2 * s) < 1e-9),
              lambda d, s: f"{d} * {d} = 2 * {s}?"),

            # Biết nửa chu vi p và đường chéo d: (a - b)² = 2d² - p², vuông khi p² = 2d²
            R(["nua_chu_vi", "duong_cheo"], "la_vuong", "kết luận",
              "hình chữ nhật là hình vuông khi p * p = 2 * d * d "
              "với p là nửa chu vi, d là đường chéo",
              lambda p, d: float(abs(p * p - 2 * d * d) < 1e-9),
              lambda p, d: f"{p} * {p} = 2 * {d} * {d}?"),
            
            R(["dai", "rong"], "chu_vi", "P",
              "P = 2 * (a + b) với a là chiều dài, b là chiều rộng",
              lambda a, b: 2 * (a + b), lambda a, b: f"2 * ({a} + {b})"),
            R(["dai", "rong"], "nua_chu_vi", "p",
              "p = a + b với a là chiều dài, b là chiều rộng",
              lambda a, b: a + b, lambda a, b: f"{a} + {b}"),
            R(["nua_chu_vi"], "chu_vi", "P", "P = 2 * p với p là nửa chu vi",
              lambda p: 2 * p, lambda p: f"2 * {p}"),
            R(["chu_vi"], "nua_chu_vi", "p", "p = P / 2 với P là chu vi",
              lambda P: P / 2, lambda P: f"{P} / 2"),
            R(["dai", "rong"], "dien_tich", "S",
              "S = a * b với a là chiều dài, b là chiều rộng",
              lambda a, b: a * b, lambda a, b: f"{a} * {b}"),
            R(["dai", "rong"], "duong_cheo", "d",
              "d = √(a * a + b * b) với a là chiều dài, b là chiều rộng",
              lambda a, b: _sqrt(a * a + b * b),
              lambda a, b: f"√({a} * {a} + {b} * {b})"),
            R(["nua_chu_vi", "rong"], "dai", "a",
              "a = p - b với p là nửa chu vi, b là chiều rộng",
              lambda p, b: p - b, lambda p, b: f"{p} - {b}"),
            R(["nua_chu_vi", "dai"], "rong", "b",
              "b = p - a với p là nửa chu vi, a là chiều dài",
              lambda p, a: p - a, lambda p, a: f"{p} - {a}"),
            R(["dien_tich", "rong"], "dai", "a",
              "a = S / b với S là diện tích, b là chiều rộng",
              lambda s, b: s / b, lambda s, b: f"{s} / {b}"),
            R(["dien_tich", "dai"], "rong", "b",
              "b = S / a với S là diện tích, a là chiều dài",
              lambda s, a: s / a, lambda s, a: f"{s} / {a}"),
            R(["duong_cheo", "rong"], "dai", "a",
              "a = √(d * d - b * b) với d là đường chéo, b là chiều rộng",
              lambda d, b: _sqrt(d * d - b * b),
              lambda d, b: f"√({d} * {d} - {b} * {b})"),
            R(["duong_cheo", "dai"], "rong", "b",
              "b = √(d * d - a * a) với d là đường chéo, a là chiều dài",
              lambda d, a: _sqrt(d * d - a * a),
              lambda d, a: f"√({d} * {d} - {a} * {a})"),
            R(["nua_chu_vi", "duong_cheo"], "dien_tich", "S",
              "S = (p * p - d * d) / 2 với p là nửa chu vi, d là đường chéo",
              lambda p, d: (p * p - d * d) / 2,
              lambda p, d: f"({p} * {p} - {d} * {d}) / 2"),
            R(["duong_cheo", "dien_tich"], "nua_chu_vi", "p",
              "p = √(d * d + 2 * S) với d là đường chéo, S là diện tích",
              lambda d, s: _sqrt(d * d + 2 * s),
              lambda d, s: f"√({d} * {d} + 2 * {s})"),
            R(["nua_chu_vi", "dien_tich"], "dai", "a",
              "a = (p + √(p * p - 4 * S)) / 2 với p là nửa chu vi, S là diện tích "
              "(quy ước chiều dài >= chiều rộng)",
              lambda p, s: (p + _sqrt(p * p - 4 * s)) / 2,
              lambda p, s: f"({p} + √({p} * {p} - 4 * {s})) / 2"),
            R(["nua_chu_vi", "dien_tich"], "rong", "b",
              "b = (p - √(p * p - 4 * S)) / 2 với p là nửa chu vi, S là diện tích "
              "(quy ước chiều dài >= chiều rộng)",
              lambda p, s: (p - _sqrt(p * p - 4 * s)) / 2,
              lambda p, s: f"({p} - √({p} * {p} - 4 * {s})) / 2"),
        ],
    }

    # ------------------------------------------------------------------
    def __init__(self):
        all_alias = {**self.ALIASES, **self.SHAPE_ALIASES}
        pairs = {(self._strip(al), canon)
                 for canon, als in all_alias.items() for al in als}
        # dài trước: "do dai canh" thắng "canh", "hinh chu nhat" thắng "chu nhat"
        self.alias_list = sorted(pairs, key=lambda p: -len(p[0]))
        # So khớp gần đúng chỉ cho từ >= 5 ký tự để tránh sửa nhầm ("trong" != "rong")
        self.fuzzy_words = {al: canon for al, canon in self.alias_list
                            if " " not in al and len(al) >= 5}

    @staticmethod
    def _strip(text):
        text = text.lower().replace("đ", "d")
        text = unicodedata.normalize("NFD", text)
        return "".join(c for c in text if unicodedata.category(c) != "Mn")

    @staticmethod
    def _fmt(v):
        return int(round(v)) if abs(v - round(v)) < 1e-9 else round(v, 2)

    # ---------------- Chuẩn hóa ----------------
    def normalize(self, text):
        t = self._strip(text)
        t = re.sub(r"(\d),(\d)", r"\1.\2", t)        # 3,5 -> 3.5
        t = re.sub(r"[_\-]+", " ", t)
        t = re.sub(r"\s+", " ", t).strip()

        for sym, canon in self.SYMBOLS.items():       # "a = 5" -> "sym_a 5"
            t = re.sub(rf"\b{sym}\s*[=:]\s*(?=\d)", f"{canon} ", t)

        for alias, canon in self.alias_list:
            t = re.sub(rf"\b{re.escape(alias)}\b", canon, t)

        # Sửa lỗi chính tả: thử ghép 2 từ liền nhau trước, rồi từng từ
        words, out, i = t.split(), [], 0
        ok = lambda w: w.isalpha()
        while i < len(words):
            w = words[i]
            if i + 1 < len(words) and ok(w) and ok(words[i + 1]):
                m = get_close_matches(w + words[i + 1], self.fuzzy_words, n=1, cutoff=0.85)
                if m:
                    out.append(self.fuzzy_words[m[0]])
                    i += 2
                    continue
            if ok(w) and len(w) >= 5:
                m = get_close_matches(w, self.fuzzy_words, n=1, cutoff=0.85)
                if m:
                    w = self.fuzzy_words[m[0]]
            out.append(w)
            i += 1
        return " ".join(out)

    # ---------------- Nhận dạng hình ----------------
    def detect_shape(self, t):
        cn, hv = "shape_cn" in t, "shape_hv" in t
        if cn and not hv:
            return "chu_nhat"
        if hv and not cn:
            return "vuong"
        if cn and hv:
            return None                               # nhắc cả hai -> hỏi lại
        has = lambda w: re.search(rf"\b{w}\b", t)
        if has("dai") or has("rong") or has("sym_b") or has("nua_chu_vi"):
            return "chu_nhat"
        if has("canh"):
            return "vuong"
        return None

    # ---------------- Phân tích câu hỏi ----------------
    def parse_input(self, text):
        t = self.normalize(text)
        shape = self.detect_shape(t)
        if shape is None:
            return None, {}, []

        if shape == "vuong":                          # hình vuông: dài/rộng đều là cạnh
            t = re.sub(r"\b(dai|rong|sym_a)\b", "canh", t)
        else:
            t = re.sub(r"\bsym_a\b", "dai", t)
            t = re.sub(r"\bsym_b\b", "rong", t)

        attrs = self.SHAPES[shape]["attrs"]
        names = "|".join(self.ALIASES)
        filler = rf"(?:(?!\b(?:{names})\b)[^\d.,;?!]){{0,30}}?"

        knowns, targets = {}, []
        for attr in attrs:
            m = re.search(rf"\b{attr}\b{filler}{self.NUM}", t)
            if m:
                knowns[attr] = abs(float(m.group(1)))
        for attr in attrs:
            if attr not in knowns and re.search(rf"\b{attr}\b", t):
                targets.append(attr)
        if not targets and knowns:
            targets = [a for a in attrs if a not in knowns]
        return shape, knowns, targets

    # ---------------- Suy diễn tiến ----------------
    def infer(self, shape, knowns):
        steps, invalid = [], False
        while True:
            updated = False
            for r in self.RULES[shape]:
                if r["give"] in knowns or any(n not in knowns for n in r["need"]):
                    continue
                xs = [knowns[n] for n in r["need"]]
                try:
                    v = r["fn"](*xs)
                except (ZeroDivisionError, ValueError, OverflowError):
                    v = None
                if v is None or v < -1e-9:           # không hợp lệ -> bỏ qua luật
                    invalid = True
                    continue
                v = max(v, 0.0)
                knowns[r["give"]] = v
                steps.append({"rule": r, "xs": xs, "value": v})
                updated = True
            if not updated:
                break
        return knowns, steps, invalid

    # ---------------- Truy ngược & giải thích ----------------
    def trace(self, target, given, steps):
        by_give = {s["rule"]["give"]: s for s in steps}
        used_given, used_steps = [], []

        def visit(attr):
            if attr in given:
                if attr not in used_given:
                    used_given.append(attr)
                return
            st = by_give[attr]
            for n in st["rule"]["need"]:
                visit(n)
            if not any(st is s for s in used_steps):
                used_steps.append(st)

        visit(target)
        return used_given, used_steps

    def explain(self, shape, target, given, steps):
        f, L = self._fmt, self.LABEL
        sname = self.SHAPES[shape]["name"]
        used_given, used_steps = self.trace(target, given, steps)

        lines = [f"Ta có {L[k]} {sname} = {f(given[k])}" for k in used_given]
        for st in used_steps:
            r = st["rule"]
            lines.append(f"Áp dụng công thức tính {L[r['give']]} {sname} "
                         f"{r['expl']} ta được")
            args = [str(f(x)) for x in st["xs"]]
            lines.append(f"{r['sym']} = {r['expr'](*args)} = {f(st['value'])}")
        if not used_steps:
            lines.append(f"Vậy {L[target]} {sname} = {f(given[target])}")
        return "\n".join(lines)

    # ---------------- Trả lời ----------------
    def reply(self, user_input):
        shape, knowns, targets = self.parse_input(user_input)
        if shape is None:
            return ("Mình chưa xác định được bạn hỏi về hình vuông hay hình chữ nhật. "
                    "Bạn ghi rõ giúp mình nhé (ví dụ: 'hình chữ nhật có chiều dài 8, "
                    "chiều rộng 5, tìm diện tích').")
        if not knowns:
            return ("Không thể tìm thấy: thiếu dữ kiện kèm giá trị. "
                    "Ví dụ: 'hình vuông có cạnh là 5, tìm diện tích'.")

        given = dict(knowns)
        full, steps, invalid = self.infer(shape, dict(knowns))
        sname = self.SHAPES[shape]["name"]

        blocks = [f"Bài toán về {sname}."]
        for t in targets:
            if t in full:
                blocks.append(self.explain(shape, t, given, steps))
            elif invalid:
                blocks.append(f"Không tính được {self.LABEL[t]}: dữ kiện không hợp lệ "
                              f"(ví dụ ra số âm hoặc căn của số âm).")
            else:
                blocks.append(f"Không thể tính {self.LABEL[t]} từ dữ kiện đã cho.")
        return "\n\n".join(blocks[:1]) + "\n" + "\n\n".join(blocks[1:])


if __name__ == "__main__":
    bot = ShapeExpertChatbot()
    while True:
        prompt = input("Nhap prompt (nhap 0 de thoat): ")
        if prompt == "0":
            break
        print(bot.reply(prompt))
        print()