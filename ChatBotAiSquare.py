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
        #Tap tri thuc va muc tieu
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
        while True:
            updated = False
            if "canh" in knowns and knowns["canh"] >= 0:
                a = knowns["canh"]
                if "chu_vi" not in knowns:
                    knowns["chu_vi"] = 4 * a; updated = True
                if "dien_tich" not in knowns:
                    knowns["dien_tich"] = a ** 2; updated = True
            if "chu_vi" in knowns and knowns["chu_vi"] >= 0:
                p = knowns["chu_vi"]
                if "canh" not in knowns:
                    knowns["canh"] = p / 4; updated = True
                if "dien_tich" not in knowns:
                    knowns["dien_tich"] = (p / 4) ** 2; updated = True
            if "dien_tich" in knowns and knowns["dien_tich"] >= 0:
                s = knowns["dien_tich"]
                if "canh" not in knowns:
                    knowns["canh"] = math.sqrt(s); updated = True
                if "chu_vi" not in knowns:
                    knowns["chu_vi"] = 4 * math.sqrt(s); updated = True
            if not updated:
                break
        return knowns

    def reply(self, user_input):
        #Chuyen input thanh tap tri thuc va muc tieu
        knowns, targets = self.parse_input(user_input)
        if not knowns:
            return "Output = [Không thể tìm thấy: thiếu dữ liệu. Ví dụ: 'cạnh là 5']"
        full = self.infer(dict(knowns))
        results, missing = [], []
        for t in targets:
            if t in full:
                v = full[t]
                v = int(v) if float(v).is_integer() else round(v, 2)
                results.append(f"{t.replace('_', ' ').capitalize()}: {v}")
            else:
                missing.append(t.replace("_", " "))
        if results:
            out = ", ".join(results)
            if missing:
                out += f" (Không thể tính: {', '.join(missing)})"
            return f"Output = [{out}]"
        return "Output = [Không thể tìm thấy: dữ liệu không đủ để tính]"


bot = SquareExpertChatbot()
while True:
    prompt = input("Nhap prompt (nhap 0 de thoat): ")
    if prompt == "0":
        break
    print(bot.reply(prompt))