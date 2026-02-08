import random
import string

# 数字3つとアルファベット4つをそれぞれランダムに生成して、ハイフンで繋ぐ
digits = ''.join(random.choices(string.digits, k=3))
letters = ''.join(random.choices(string.ascii_lowercase, k=4))

result = f"{digits}-{letters}"
print(result)
