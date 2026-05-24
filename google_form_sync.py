#!/usr/bin/env python3
"""
Google Forms 订阅者管理脚本
读取表单回应，获取订阅者邮箱列表
"""
import os
import json
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 配置
SCOPES = ['https://www.googleapis.com/auth/forms.body.readonly', 
          'https://www.googleapis.com/auth/spreadsheets.readonly']
FORM_ID = "1FAIpQLSdfzHlWE_jGfdRekPDRtGr0JHqJIshEojXGAg_Ea4pBomd8Pw"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")
CREDS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")

def get_credentials():
    """获取 Google API 凭证"""
    creds = None
    
    # 读取已保存的 token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
    
    # 如果没有有效凭证，需要授权
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_FILE):
                print("❌ 请先下载 Google OAuth 凭证文件 (credentials.json)")
                print("""
步骤：
1. 打开 https://console.cloud.google.com/
2. 创建项目（或选择已有项目）
3. 启用 Google Sheets API 和 Google Forms API
4. 创建 OAuth 2.0 客户端凭证（桌面应用）
5. 下载 credentials.json 并放到此目录
                """)
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 保存凭证
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    
    return creds

def get_form_responses():
    """获取表单回应"""
    creds = get_credentials()
    if not creds:
        return []
    
    try:
        # 使用 Sheets API 读取表单回应
        service = build('sheets', 'v4', credentials=creds)
        
        # 获取表单对应的 spreadsheet ID
        # 表单回应会自动创建 spreadsheet
        spreadsheet_id = FORM_ID.replace('1FAIpQL', '1fAHpQL')
        
        # 尝试直接获取
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range="Form Responses1!A:A").execute()
        
        values = result.get('values', [])
        
        # 提取邮箱（第一列通常是时间戳，最后一列是邮箱）
        emails = []
        for i, row in enumerate(values):
            if i == 0:  # 跳过表头
                continue
            if row:
                # 假设最后一列是邮箱
                email = row[-1].strip()
                if '@' in email and email not in emails:
                    emails.append(email)
        
        return emails
        
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []

def load_subscribers():
    """从本地文件加载订阅者列表"""
    subscribers_file = os.path.join(SCRIPT_DIR, "subscribers.json")
    if os.path.exists(subscribers_file):
        with open(subscribers_file, 'r') as f:
            return json.load(f)
    return []

def save_subscribers(subscribers):
    """保存订阅者列表"""
    subscribers_file = os.path.join(SCRIPT_DIR, "subscribers.json")
    with open(subscribers_file, 'w') as f:
        json.dump(subscribers, f, indent=2)

def sync_subscribers():
    """同步 Google Form 订阅者"""
    print("🔄 正在同步 Google Form 订阅者...")
    
    emails = get_form_responses()
    
    if not emails:
        print("⚠️ 未获取到新订阅者")
        return load_subscribers()
    
    # 合并去重
    existing = load_subscribers()
    all_emails = list(set(existing + emails))
    
    save_subscribers(all_emails)
    print(f"✅ 已同步 {len(emails)} 位新订阅者，总计 {len(all_emails)} 位")
    
    return all_emails

if __name__ == "__main__":
    subscribers = sync_subscribers()
    print("\n📧 订阅者列表:")
    for email in subscribers:
        print(f"  - {email}")
