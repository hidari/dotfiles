import random
import string
import sys

def generate_random_string():
    """数字3つとアルファベット4つをハイフンで繋いだ文字列を生成する"""
    digits = ''.join(random.choices(string.digits, k=3))
    letters = ''.join(random.choices(string.ascii_lowercase, k=4))
    return f"{digits}-{letters}"

def main():
    # 引数が指定されてなかったらデフォルトで1個生成
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    for _ in range(count):
        print(generate_random_string())

if __name__ == "__main__":
    main()
