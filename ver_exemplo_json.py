
import json
import re

def _repair_quotes(s: str) -> str:
    result = []
    i = 0
    in_string = False
    while i < len(s):
        char = s[i]
        if char == '"':
            is_structural = False
            prev_part = s[max(0, i-10):i]
            next_part = s[i+1:i+10]
            if re.search(r'[ {\[,]\s*$', prev_part): is_structural = True
            elif re.match(r'^\s*:', next_part): is_structural = True
            elif re.search(r':\s*$', prev_part): is_structural = True
            elif re.match(r'^\s*[,}\]]', next_part): is_structural = True
            
            if in_string and not is_structural:
                result.append('\\"')
            else:
                result.append('"')
                in_string = not in_string
        else:
            result.append(char)
            if char == '\\' and i + 1 < len(s) and s[i+1] == '"':
                result.append('"')
                i += 1
        i += 1
    return "".join(result)

# Exemplo de JSON que o Gemini costuma retornar com erro
bad_json = """{
  "title": "Mastering a Weight Loss Lifestyle",
  "html": "<div class=\\"myth-fact\\">This is a \\"test\\" of quotes</div>",
  "meta_description": "Discover how to \\"burn\\" calories without stress"
}"""

# Simulando o erro que você recebeu (aspas não escapadas no meio da string)
broken_json = bad_json.replace('\\"', '"')

print("--- JSON QUEBRADO (Simulado) ---")
print(broken_json)

try:
    json.loads(broken_json)
except Exception as e:
    print(f"\nErro de parse original: {e}")

print("\n--- TENTANDO REPARAR ---")
repaired = _repair_quotes(broken_json)
print(repaired)

try:
    data = json.loads(repaired)
    print("\nSucesso! JSON parseado corretamente.")
    print(f"Título: {data['title']}")
except Exception as e:
    print(f"\nFalha no reparo: {e}")
