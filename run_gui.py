#!/usr/bin/env python3
"""启动猛禽迁徙预测系统 GUI"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from falcon_gui import main

if __name__ == '__main__':
    main()
