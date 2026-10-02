import math
import re
import unicodedata
from difflib import get_close_matches


class SquareExpertChatbot:
    NUM = r"([-+]?\d*\.\d+|\d+)"

    # Từ chuẩn -> các biến thể người dùng có thể gõ (đã bỏ dấu, viết thường)
    ALIASES = {
        "chu_vi":    ["chu vi", "chuvi", "chu v", "chu vy", "cv", "chu ki"],
        "dien_tich": ["dien tich", "dientich", "dien tic", "dien t", "dt"],
        "canh":      ["do dai canh", "canh", "cnh", "cạnh"],
    }
    # Ký hiệu 1 chữ cái: chỉ nhận khi có dạng "a = 5", "s: 25"
    SYMBOLS = {"a": "canh", "p": "chu_vi", "s": "dien_tich"}
    
    LABEL = {"canh": "cạnh", "chu_vi": "chu vi", "dien_tich": "diện tích"}
    
    # Tap luat
    # Mỗi luật: biết `need` -> tính `give`
    RULES = [
        dict(need="canh", give="chu_vi", sym="P",
             expl="P = 4 * a với a là cạnh",
             fn=lambda x: 4 * x,
             expr=lambda s: f"4 * {s}"),
        dict(need="canh", give="dien_tich", sym="S",
             expl="S = a * a với a là cạnh",
             fn=lambda x: x * x,
             expr=lambda s: f"{s} * {s}"),
        dict(need="chu_vi", give="canh", sym="a",
             expl="a = P / 4 với P là chu vi",
             fn=lambda x: x / 4,
             expr=lambda s: f"{s} / 4"),
        dict(need="dien_tich", give="canh", sym="a",
             expl="a = √S với S là diện tích",
             fn=lambda x: math.sqrt(x),
             expr=lambda s: f"√{s}"),
    ]

    def __init__(self):
        # Danh sách (biến thể, từ chuẩn), xếp dài trước để "do dai canh" thắng "canh"
        pairs = [(self._strip(al), canon)
                 for canon, als in self.ALIASES.items() for al in als]
        
        self.alias_list = sorted(set(pairs), key=lambda p: -len(p[0]))
        # Các từ đơn (>=3 ký tự) dùng cho so khớp gần đúng (gõ sai chính tả)
        self.fuzzy_words = {al: canon for al, canon in self.alias_list
                            if " " not in al and len(al) >= 3}
        self.fuzzy_words.update({"chuvi": "chu_vi", "dientich": "dien_tich"})

    @staticmethod
    def _strip(text):
        """Viết thường + bỏ dấu tiếng Việt"""
        text = text.lower().replace("đ", "d")
        text = unicodedata.normalize("NFD", text)
        return "".join(c for c in text if unicodedata.category(c) != "Mn")
    
    @staticmethod
    def _fmt(v):
        return int(v) if float(v).is_integer() else round(v, 2)
    # chuan hoa input
    def normalize(self, text):
        t = self._strip(text)
        t = re.sub(r"[_\-]+", " ", t)           # chu_vi, chu-vi -> chu vi
        t = re.sub(r"\s+", " ", t).strip()

        # 1. Ký hiệu 1 chữ cái: "a = 5" -> "canh 5"
        for sym, canon in self.SYMBOLS.items():
            t = re.sub(rf"\b{sym}\s*[=:]\s*(?=\d)", f"{canon} ", t)

        # 2. Thay các biến thể bằng từ chuẩn (có ranh giới từ)
        for alias, canon in self.alias_list:
            t = re.sub(rf"\b{re.escape(alias)}\b", canon, t)

        # 3. Sửa lỗi chính tả nhẹ cho từ còn lại (vd: "dien tihc", "chuvii")
        canon_tokens = set(self.ALIASES)
        words = []
        for w in t.split():
            if w not in canon_tokens and len(w) >= 3 and not w.isdigit():
                m = get_close_matches(w, self.fuzzy_words, n=1, cutoff=0.8)
                if m:
                    w = self.fuzzy_words[m[0]]
            words.append(w)
        return " ".join(words)

    def parse_input(self, text):
        t = self.normalize(text)
        #Tap tri thuc da biet va muc tieu
        knowns, targets = {}, []

        names = "|".join(self.ALIASES)  # canh|chu_vi|dien_tich
        
        # Đoạn chữ xen giữa: không có số, không có dấu ngắt câu, không chứa từ khóa khác
        filler = rf"(?:(?!\b(?:{names})\b)[^\d.,;?!]){{0,30}}?"

        for attr in self.ALIASES:
            m = re.search(rf"\b{attr}\b{filler}{self.NUM}", t)
            if m:
                knowns[attr] = float(m.group(1))

        for attr in self.ALIASES:
            if attr not in knowns and re.search(rf"\b{attr}\b", t):
                targets.append(attr)

        if not targets and knowns:
            targets = [a for a in self.ALIASES if a not in knowns]
        return knowns, targets

    # Suy dien tien
    def infer(self, knowns):
        """Suy diễn tiến: lặp áp dụng luật đến khi không sinh thêm được gì."""
        steps = []
        while True:
            updated = False
            #Duyet qua tung luat trong RULES
            for r in self.RULES:
                #Neu du kien can cho cong thuc nam trong tap tri thuc va
                #ket qua se co duoc khi ap dung cong thuc chua co trong tap knowns
                #Thi ta su dung cong thuc do tinh ra ket qua va them no vao tap tri thuc
                if r["need"] in knowns and r["give"] not in knowns:
                    x = knowns[r["need"]]
                    if x < 0:                      # số âm: không hợp lệ
                        continue
                    v = r["fn"](x)
                    knowns[r["give"]] = v
                    steps.append({"rule": r, "x": x, "value": v})
                    updated = True
            if not updated:
                break
        return knowns, steps
    
    def trace(self, target, given, steps):
        """Truy ngược từ target: chỉ giữ dữ kiện và bước thật sự cần."""
        by_give = {s["rule"]["give"]: s for s in steps}
        used_given, used_steps = [], []

        def visit(attr):
            if attr in given:
                if attr not in used_given:
                    used_given.append(attr)
                return
            st = by_give[attr]
            visit(st["rule"]["need"])              # truy tiếp dữ kiện của bước này
            if st not in used_steps:
                used_steps.append(st)              # thêm sau => đúng thứ tự giải

        visit(target)
        return used_given, used_steps
    
    def explain(self, target, given, steps):
        f, L = self._fmt, self.LABEL
        used_given, used_steps = self.trace(target, given, steps)

        lines = [f"Ta có {L[k]} hình vuông = {f(given[k])}" for k in used_given]
        for st in used_steps:
            r = st["rule"]
            lines.append(f"Áp dụng công thức tính {L[r['give']]} hình vuông "
                         f"{r['expl']} ta được")
            lines.append(f"{r['sym']} = {r['expr'](str(f(st['x'])))} = {f(st['value'])}")
        if not used_steps:                         # target vốn đã được cho sẵn
            lines.append(f"Vậy {L[target]} = {f(given[target])}")
        return "\n".join(lines)
    
    def reply(self, user_input):
        knowns, targets = self.parse_input(user_input)
        if not knowns:
            return "Không thể tìm thấy: thiếu dữ liệu. Ví dụ: 'cạnh là 5'"

        given = dict(knowns)
        full, steps = self.infer(dict(knowns))

        blocks = []
        for t in targets:
            if t in full:
                blocks.append(self.explain(t, given, steps))
            else:
                blocks.append(f"Không thể tính {self.LABEL[t]} từ dữ kiện đã cho.")
        return "\n\n".join(blocks)


bot = SquareExpertChatbot()
while True:
    prompt = input("Nhap prompt (nhap 0 de thoat): ")
    if prompt == "0":
        break
    print(bot.reply(prompt))