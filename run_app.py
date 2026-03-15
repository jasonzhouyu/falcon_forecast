import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 运行app.py
from app.app import main

if __name__ == '__main__':
    main()
