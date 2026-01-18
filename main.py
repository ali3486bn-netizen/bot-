#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import asyncio
import re
import json
import shutil
import time
import datetime
import random
import base64
import ipaddress
import struct
import secrets
import csv
import traceback
from pathlib import Path
from typing import Type, Optional
from datetime import timedelta

# Check and install required modules
def install_modules():
    required_modules = [
        'telethon',
        'kvsqlite',
        'pyrogram',
        'aiosqlite',
    ]

    for module in required_modules:
        try:
            if module == 'telethon':
                import telethon
            elif module == 'kvsqlite':
                import kvsqlite
            elif module == 'pyrogram':
                import pyrogram
            elif module == 'aiosqlite':
                import aiosqlite
        except ImportError:
            print(f'Installing {module}...')
            os.system(f'pip install {module}')

# Install modules if needed
install_modules()

# Now import everything
from kvsqlite.sync import Client as uu
from telethon.sessions import StringSession
from telethon import TelegramClient, events, functions, types, Button
from telethon.tl.types import (
    KeyboardButtonUrl, KeyboardButton, ReplyInlineMarkup,
    DocumentAttributeFilename, InputPeerUser, InputPeerChannel
)
from telethon.errors import (
    ApiIdInvalidError, PhoneNumberInvalidError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, SessionPasswordNeededError, PasswordHashInvalidError
)
from telethon.errors.rpcerrorlist import UserDeactivatedBanError
from telethon.tl.functions.account import GetAuthorizationsRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.channels import GetParticipantRequest
from pyrogram import Client, enums

# Messages dictionary - تحديث العملة من "عملات" إلى "$"
msgs = {
    "START_MESSAGE":
        u"**🟢︙ مرحبًا بك عزيزي في بوت الحسابات**\n"
        u"🛒︙ بوت بيع وشراء الحسابات الوهمية \n"
        u"🆔︙ ايديك : `{}`\n"
        u"💰︙ رصيدك : {:.2f} $\n"  # تغيير من "عملات" إلى "$" وإضافة تنسيق عشري
        u"**⚙️︙ يرجى استخدام الأزرار التالية :**",

    "ADMIN_MESSAGE":
        u"**🚀︙ مرحبا بك عزيزي المالك**",

    "TRANSFER_MESSAGE":
        u"**✅︙مرحبا بك عزيزي في قسم التحويل** \n"
        u"♻️︙يتم التحويل الي العضو المراد بالضبط \n"
        u"👨‍✈️︙التحويل يكون أمن بنسبه كبيره \n"
        u"〽️︙عمولة التحويل ↫ 2% \n"
        u"**🆔︙قم بارسال ايدي العضو المراد تحويل النقاط اليه : **",

    "BUY_MESSAGE":
        u"**✅︙هل انت متاكد من شراء الرقم ؟**"
        u"\n ⌁︙معلومات الرقم :-"
        u"\n"
        u"🌎︙ الدولة: {}\n"
        u"💰︙ سعر الرقم : {:.2f} $\n"  # تغيير من "عملات" إلى "$" وإضافة تنسيق عشري
        u"**🚀︙اذا تريد الشراء اضغط (تأكيد ✅) و اذا لا تريد اضغط (الغاء ❌)**",

    "COUNTRY_LIST":
        u"🚀︙**قم بإختيار الدولة التي تريد شراؤها**.",

    "TRUST_MESSAGE":
        u"**📢 تم شراء حساب جديد من البوت**\n\n"
        u"🌍︙ الدولة: {}\n"
        u"📱︙ المنصة: تليجرام\n"
        u"📞︙ الرقم: +{}...\n"
        u"💰︙ السعر: {:.2f} $\n"  # تغيير من "عملات" إلى "$" وإضافة تنسيق عشري
        u"👤︙ العميل: {}...\n"
        u"🔑︙ كود التفعيل: `{}`\n"
        u"✅︙ الحالة: تم التفعيل\n\n"
        u"📅︙ التاريخ والوقت: {}",

    "MAINTENANCE_MESSAGE":
        u"**🛠️ البوت تحت الصيانة حاليًا**\n\n"
        u"🔧︙ البوت غير متاح للاستخدام حاليًا\n"
        u"👨‍💻︙ فريق العمل يقوم بإجراء الصيانة اللازمة\n"
        u"🕐︙ الرجاء المحاولة مرة أخرى لاحقًا\n"
        u"🙏︙ نعتذر للإزعاج وشكرًا لتفهمكم"
}

# Session Converter Classes
class ValidationError(Exception):
    pass

SCHEMAT = """
CREATE TABLE version (version integer primary key);

CREATE TABLE sessions (
    dc_id integer primary key,
    server_address text,
    port integer,
    auth_key blob,
    takeout_id integer
);

CREATE TABLE entities (
    id integer primary key,
    hash integer not null,
    username text,
    phone integer,
    name text,
    date integer
);

CREATE TABLE sent_files (
    md5_digest blob,
    file_size integer,
    type integer,
    id integer,
    hash integer,
    primary key(md5_digest, file_size, type)
);

CREATE TABLE update_state (
    id integer primary key,
    pts integer,
    qts integer,
    date integer,
    seq integer
);
"""

class TeleSession:
    _STRUCT_PREFORMAT = '>B{}sH256s'
    CURRENT_VERSION = '1'
    TABLES = {
        "sessions": {
            "dc_id", "server_address", "port", "auth_key", "takeout_id"
            },
        "entities": {"id", "hash", "username", "phone", "name", "date"},
        "sent_files": {"md5_digest", "file_size", "type", "id", "hash"},
        "update_state": {"id", "pts", "qts", "date", "seq"},
        "version": {"version"},
    }

    def __init__(
        self,
        *,
        dc_id: int,
        auth_key: bytes,
        server_address: Optional[str] = None,
        port: Optional[int] = None,
        takeout_id: Optional[int] = None
    ):
        self.dc_id = dc_id
        self.auth_key = auth_key
        self.server_address = server_address
        self.port = port
        self.takeout_id = takeout_id

    @classmethod
    def from_string(cls, string: str):
        string = string[1:]
        ip_len = 4 if len(string) == 352 else 16
        dc_id, ip, port, auth_key = struct.unpack(
            cls._STRUCT_PREFORMAT.format(ip_len), cls.decode(string)
        )
        server_address = ipaddress.ip_address(ip).compressed
        return cls(
            auth_key=auth_key,
            dc_id=dc_id,
            port=port,
            server_address=server_address,
        )

    @staticmethod
    def encode(x: bytes) -> str:
        return base64.urlsafe_b64encode(x).decode('ascii')

    @staticmethod
    def decode(x: str) -> bytes:
        return base64.urlsafe_b64decode(x)

    def to_string(self) -> str:
        if self.server_address is None:
            from pyrogram.session.internals.data_center import DataCenter
            self.server_address, self.port = DataCenter(
                self.dc_id, False, False, False
            )
        ip = ipaddress.ip_address(self.server_address).packed
        return self.CURRENT_VERSION + self.encode(struct.pack(
            self._STRUCT_PREFORMAT.format(len(ip)),
            self.dc_id,
            ip,
            self.port,
            self.auth_key
        ))

SCHEMA = """
CREATE TABLE sessions (
    dc_id     INTEGER PRIMARY KEY,
    api_id    INTEGER,
    test_mode INTEGER,
    auth_key  BLOB,
    date      INTEGER NOT NULL,
    user_id   INTEGER,
    is_bot    INTEGER
);

CREATE TABLE peers (
    id             INTEGER PRIMARY KEY,
    access_hash    INTEGER,
    type           INTEGER NOT NULL,
    username       TEXT,
    phone_number   TEXT,
    last_update_on INTEGER NOT NULL DEFAULT (CAST(STRFTIME('%s', 'now') AS INTEGER))
);

CREATE TABLE version (
    number INTEGER PRIMARY KEY
);

CREATE INDEX idx_peers_id ON peers (id);
CREATE INDEX idx_peers_username ON peers (username);
CREATE INDEX idx_peers_phone_number ON peers (phone_number);

CREATE TRIGGER trg_peers_last_update_on
    AFTER UPDATE
    ON peers
BEGIN
    UPDATE peers
    SET last_update_on = CAST(STRFTIME('%s', 'now') AS INTEGER)
    WHERE id = NEW.id;
END;
"""

class PyroSession:
    OLD_STRING_FORMAT = ">B?256sI?"
    OLD_STRING_FORMAT_64 = ">B?256sQ?"
    STRING_SIZE = 351
    STRING_SIZE_64 = 356
    STRING_FORMAT = ">BI?256sQ?"
    TABLES = {
        "sessions": {"dc_id", "test_mode", "auth_key", "date", "user_id", "is_bot"},
        "peers": {"id", "access_hash", "type", "username", "phone_number", "last_update_on"},
        "version": {"number"}
    }

    def __init__(
        self,
        *,
        dc_id: int,
        auth_key: bytes,
        user_id: Optional[int] = None,
        is_bot: bool = False,
        test_mode: bool = False,
        api_id: Optional[int] = None,
        **kw
    ):
        self.dc_id = dc_id
        self.auth_key = auth_key
        self.user_id = user_id
        self.is_bot = is_bot
        self.test_mode = test_mode
        self.api_id = api_id

    @classmethod
    def from_string(cls, session_string: str):
        if len(session_string) in [cls.STRING_SIZE, cls.STRING_SIZE_64]:
            string_format = cls.OLD_STRING_FORMAT_64

            if len(session_string) == cls.STRING_SIZE:
                string_format = cls.OLD_STRING_FORMAT

            api_id = None
            dc_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                string_format,
                base64.urlsafe_b64decode(
                    session_string + "=" * (-len(session_string) % 4)
                )
            )
        else:
            dc_id, api_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                cls.STRING_FORMAT,
                base64.urlsafe_b64decode(
                    session_string + "=" * (-len(session_string) % 4)
                )
            )

        return cls(
            dc_id=dc_id,
            api_id=api_id,
            auth_key=auth_key,
            user_id=user_id,
            is_bot=is_bot,
            test_mode=test_mode,
        )

    def to_string(self) -> str:
        packed = struct.pack(
            self.STRING_FORMAT,
            self.dc_id,
            self.api_id or 0,
            self.test_mode,
            self.auth_key,
            self.user_id or 9999,
            self.is_bot
        )
        return base64.urlsafe_b64encode(packed).decode().rstrip("=")

# APIData placeholder class
class APIData:
    def __init__(self, api_id, api_hash, **kwargs):
        self.api_id = api_id
        self.api_hash = api_hash
        self.device_model = kwargs.get('device_model', '')
        self.system_version = kwargs.get('system_version', '')
        self.app_version = kwargs.get('app_version', '')
        self.lang_code = kwargs.get('lang_code', 'en')
        self.system_lang_code = kwargs.get('system_lang_code', 'en')

    def copy(self):
        return APIData(
            self.api_id,
            self.api_hash,
            device_model=self.device_model,
            system_version=self.system_version,
            app_version=self.app_version,
            lang_code=self.lang_code,
            system_lang_code=self.system_lang_code
        )

class API:
    TelegramDesktop = APIData(2040, "b18441a1ff607e10a989891a5462e627")

class SessionManager:
    def __init__(
        self,
        dc_id: int,
        auth_key: bytes,
        user_id: Optional[int] = None,
        valid: Optional[bool] = None,
        api: Type[APIData] = API.TelegramDesktop,
    ):
        self.dc_id = dc_id
        self.auth_key = auth_key
        self.user_id = user_id
        self.valid = valid
        self.api = api.copy()
        self.user = None
        self.client = None

    @classmethod
    def from_telethon_string(cls, string: str, api=API.TelegramDesktop):
        session = TeleSession.from_string(string)
        return cls(
            dc_id=session.dc_id,
            auth_key=session.auth_key,
            api=api
        )

    @classmethod
    def from_pyrogram_string(cls, string: str, api=API.TelegramDesktop):
        session = PyroSession.from_string(string)
        return cls(
            auth_key=session.auth_key,
            dc_id=session.dc_id,
            api=api,
            user_id=session.user_id,
        )

    def to_pyrogram_string(self) -> str:
        return self.pyrogram.to_string()

    def to_telethon_string(self) -> str:
        return self.telethon.to_string()

    @property
    def pyrogram(self) -> PyroSession:
        return PyroSession(
            dc_id=self.dc_id,
            auth_key=self.auth_key,
            user_id=self.user_id,
        )

    @property
    def telethon(self) -> TeleSession:
        return TeleSession(
            dc_id=self.dc_id,
            auth_key=self.auth_key,
        )

class MangSession:
    @staticmethod
    def PYROGRAM_TO_TELETHON(session_string: str):
        Session_data = SessionManager.from_pyrogram_string(session_string)
        return Session_data.to_telethon_string()

    @staticmethod
    def TELETHON_TO_PYROGRAM(session_string: str):
        Session_data = SessionManager.from_telethon_string(session_string)
        return Session_data.to_pyrogram_string()

# Helper functions
async def get_code(session):
    API_ID = 1724716
    API_HASH = "00b2d8f59c12c1b9a4bc63b70b461b2f"
    try:
        app = TelegramClient(StringSession(session), api_id=API_ID, api_hash=API_HASH)
        await app.connect()
        async for x in app.iter_messages(777000, limit=1):
            code_match = re.search(r'\b(\d{5})\b', x.text)
            if code_match:
                code = code_match.group(1)
                await app.disconnect()
                return code
            else:
                await app.disconnect()
                return "لم يتم العثور"
    except Exception as a:
        return "لم يتم العثور"

async def logout_from_session(session_string):
    """تسجيل الخروج من الجلسة"""
    try:
        API_ID = 1724716
        API_HASH = "00b2d8f59c12c1b9a4bc63b70b461b2f"
        app = TelegramClient(StringSession(session_string), api_id=API_ID, api_hash=API_HASH)
        await app.connect()
        await app.log_out()
        await app.disconnect()
        return True
    except:
        return False

async def change_password(session, old_password, new_password):
    c = Client('::memory::', in_memory=True, api_hash='00b2d8f59c12c1b9a4bc63b70b461b2f', 
               api_id=1724716, lang_code="ar", no_updates=True, session_string=session)
    try:
        await c.start()
    except:
        return False
    try:
        await c.change_cloud_password(old_password, new_password)
        await c.stop()
        return True
    except:
        return False

async def enable_password(session, new_password):
    c = Client('::memory::', in_memory=True, api_hash='00b2d8f59c12c1b9a4bc63b70b461b2f', 
               api_id=1724716, lang_code="ar", no_updates=True, session_string=session)
    try:
        await c.start()
    except:
        return False
    try:
        await c.enable_cloud_password(new_password)
        await c.stop()
        return True
    except:
        return False

async def count_ses(session):
    API_ID = 1724716
    API_HASH = "00b2d8f59c12c1b9a4bc63b70b461b2f"
    try:
        app = TelegramClient(StringSession(session), api_id=API_ID, api_hash=API_HASH)
        await app.connect()
        try:
            from telethon.tl import functions as functele
            result = await app(functele.auth.ResetAuthorizationsRequest())
        except:
            pass
        unauthorized_attempts = await app(GetAuthorizationsRequest())
        listt = []
        for i in unauthorized_attempts.authorizations:
            listt.append(i.device_model)
        await app.disconnect()
        return listt
    except Exception as a:
        print(str(a))
        return str(a)

def check_vip(user, db):
    user_id = int(user)
    users = db.get(f"vip_{user_id}")
    noww = time.time()
    if db.exists(f"vip_{user_id}"):
        last_time = users['vip']
        timeee = int(db.get(f"vip_{user_id}_time"))
        WAIT_TIMEE = int(timeee) * 24 * 60 * 60
        elapsed_time = noww - last_time
        if elapsed_time < WAIT_TIMEE:
            remaining_time = WAIT_TIMEE - elapsed_time
            return int(remaining_time)
        else:
            return None
    else:
        return None

# Main bot code
async def main():
    if not os.path.isdir('database'):
        os.mkdir('database')

    API_ID = 1724716
    API_HASH = "00b2d8f59c12c1b9a4bc63b70b461b2f"
    admin = 8267043342  # Set your admin ID here
    new_password = "2010"  # التحقق بخطوتين للحسابات التي سيتم بيعها
    token = "8242544354:AAGfkRZ_TN0lSYR3Le3UbPaWvUnXhBsTwh4"  # Replace with your bot token

    client = TelegramClient('BotSession', api_id=API_ID, api_hash=API_HASH)
    await client.start(bot_token=token)
    bot = client

    # Create DataBase
    db = uu('database/KingA.ss', 'bot')

    if not db.exists("accounts"):
        db.set("accounts", [])

    if not db.exists("countries"):
        db.set("countries", [])

    if not db.exists("bad_guys"):
        db.set("bad_guys", [])

    if not db.exists("force"):
        db.set("force", [])

    if not db.exists("admins"):
        db.set("admins", [admin])

    # إضافة نظام الصيانة
    if not db.exists("maintenance"):
        db.set("maintenance", False)  # حالة الصيانة: False = غير مفعلة

    @client.on(events.NewMessage(pattern="/sell_price", func=lambda x: x.is_private))
    async def sell_price_handler(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                return await event.reply(msgs['MAINTENANCE_MESSAGE'])
        
        bans = db.get('bad_guys') if db.exists('bad_guys') else []
        async with bot.conversation(event.chat_id) as x:
            countries = db.get("countries")
            text = ""
            for i in countries:
                text += f'{i["name"]} ({i["calling_code"]}): {i["sell_price"]:.2f} $\n'  # تغيير من "عملات" إلى "$"
            await x.send_message(text)

    @client.on(events.NewMessage(pattern="/start", func=lambda x: x.is_private))
    async def start_handler(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                return await event.reply(msgs['MAINTENANCE_MESSAGE'])
        
        bans = db.get('bad_guys') if db.exists('bad_guys') else []

        # Check force subscription
        force = db.get("force") if db.exists("force") else []
        if force:
            not_joined = []
            buttons = []
            for channel in force:
                try:
                    await client(GetParticipantRequest(
                        channel=channel,
                        participant=user_id
                    ))
                except:
                    not_joined.append(channel)

            if not_joined:
                channel_text = "\n".join([f"• @{channel}" for channel in not_joined])
                keyboard = [
                    [Button.url(f"اشترك في @{channel}", f"https://t.me/{channel}")] for channel in not_joined
                ]
                keyboard.append([Button.inline("✅ تحقق من الاشتراك", data="check_subscription")])
                await event.reply(
                    f"**⚠️︙عذراً عزيزي يجب عليك الاشتراك في القنوات التالية أولاً:**\n\n{channel_text}\n\n"
                    f"**• بعد الاشتراك اضغط على زر التحقق**",
                    buttons=keyboard
                )
                return

        keyboard = [
            [
                Button.inline("- اعدادات الارقام 🚀 .", data="ajxjao"),
            ],
            [
                Button.inline("- الاشتراك الاجباري 〽️.", data="ajxkho"), 
                Button.inline("- قسم الادمنيه 👨‍✈️.", data="aksgl"), 
            ],
            [
                Button.inline("- قسم البيع 💰 .", data="ajkofgl"),
            ],
            [
                Button.inline("- قسم الرصيد 🤍.", data="ajkcoingl"), 
                Button.inline("- قسم الحظر 🚫.", data="bbvjls"), 
            ],
            [
                Button.inline("- قناة اثباتات التسليم 🖤 .", data="set_trust_channel"),
            ],
            [
                Button.inline("- الاحصائيات 📊 .", data="statistics"),  # زر جديد للإحصائيات
            ],
            [
                Button.inline("- النسخ الاحتياطي 📁 .", data="backup_system"),  # زر جديد للنسخ الاحتياطي
            ],
            [
                Button.inline("- تعديل رسالة القوانين 🔐 .", data="edit_rules"),
            ],
            [
                Button.inline("- نظام الصيانة 🔧 .", data="maintenance_system"),
            ]
        ]

        # تعديل أزرار المستخدم
        user_info = db.get(f"user_{user_id}")
        coins = user_info["coins"] if user_info else 0
        
        # عرض الرصيد مع تنسيق عشري ثابت
        if isinstance(coins, (int, float)):
            display_coins = round(float(coins), 2)
        else:
            display_coins = 0.0
        
        buttons = [
            [
                Button.inline("- شراء رقم ✅ .", data="buy"),
            ],
            [
                Button.inline("- شحن رصيد 💰.", data="contact_admin"),
                Button.inline("- تحويل رصيد ♻️.", data="transfer"),
            ],
            [
                Button.inline("- قناة البوت 📢.", data="bot_channel"),
                Button.inline("- القوانين 🔐.", data="liscgh"),
            ],
            [
                Button.inline("- الهديه اليوميه 🎁.", data="daily_gift"),
            ]
        ]

        if user_id in bans:
            return

        if not db.exists(f"user_{user_id}"):
            members = 0
            db.set(f"user_{user_id}", {"coins": 0.0, "id": user_id})
            
            try:
                user_info = await client.get_entity(user_id)
                users = db.keys('user_%')
                for _ in users:
                    members += 1

                if user_info.username is None:
                    username = "None"
                else:
                    username = "@" + str(user_info.username)

                # إرسال إشعار للمسؤولين
                admins = db.get("admins") if db.exists("admins") else [admin]
                for admin_id in admins:
                    try:
                        await bot.send_message(
                            admin_id,
                            f'👤︙ دخل شخص جديد إلى البوت الخاص بك\n\n'
                            f'📋︙ معلومات المستخدم الجديد:\n\n'
                            f'👤︙ الاسم: <a href="tg://user?id={user_id}">{user_info.first_name}</a>\n'
                            f'📌︙ المعرف: {username}\n'
                            f'🆔︙ الأيدي: {user_id}\n\n'
                            f'👥︙ إجمالي الأعضاء: {members}',
                            parse_mode="html"
                        )
                    except Exception as e:
                        print(f"فشل إرسال إشعار للمسؤول {admin_id}: {e}")
                        
            except Exception as e:
                print(f"خطأ في الحصول على معلومات المستخدم: {e}")
            
            if user_id == admin or user_id in db.get("admins"):
                await event.reply(msgs['ADMIN_MESSAGE'], buttons=keyboard)
                await event.reply(msgs['START_MESSAGE'].format(event.chat_id, 0.0), buttons=buttons)
            else:
                await event.reply(msgs['START_MESSAGE'].format(event.chat_id, 0.0), buttons=buttons)
        else:
            coins = db.get(f"user_{user_id}")["coins"]
            # عرض الرصيد مع تنسيق عشري ثابت
            if isinstance(coins, (int, float)):
                display_coins = round(float(coins), 2)
            else:
                display_coins = 0.0
            
            if user_id == admin or user_id in db.get("admins"):
                await event.reply(msgs['ADMIN_MESSAGE'], buttons=keyboard)
                await event.reply(msgs['START_MESSAGE'].format(event.chat_id, display_coins), buttons=buttons)
            else:
                await event.reply(msgs['START_MESSAGE'].format(event.chat_id, display_coins), buttons=buttons)

    @client.on(events.CallbackQuery(pattern=b'backup_system'))
    async def backup_system_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        await event.answer(' - قسم النسخ الاحتياطي 📁', alert=False)
        await event.edit(
            '**📁︙ نظام النسخ الاحتياطي**\n\n'
            '• هنا يمكنك إدارة النسخ الاحتياطية للبوت\n'
            '• يمكنك سحب ملف النسخة الاحتياطية\n'
            '• أو رفع ملف نسخة احتياطية جديدة\n\n'
            '**اختر الإجراء المطلوب:**',
            buttons=[
                [
                    Button.inline("📥 سحب ملف نسخة", data="download_backup"),
                    Button.inline("📤 رفع ملف نسخة", data="upload_backup")
                ],
                [
                    Button.inline("📊 معلومات النسخة", data="backup_info")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'download_backup'))
    async def download_backup_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        await event.answer("📥 جاري إنشاء ملف النسخة الاحتياطية...", alert=False)
        
        try:
            # إنشاء ملف النسخة الاحتياطية
            backup_data = {}
            
            # جمع بيانات المستخدمين
            users_data = []
            users_keys = db.keys('user_%')
            total_users = 0
            for key in users_keys:
                if isinstance(key, tuple):
                    key = key[0]  # إذا كان المفتاح tuple، خذ العنصر الأول
                
                total_users += 1
                user_info = db.get(key)
                user_id_from_key = key.replace('user_', '')
                
                # محاولة الحصول على معلومات المستخدم من التليجرام
                try:
                    user_entity = await client.get_entity(int(user_id_from_key))
                    username = f"@{user_entity.username}" if user_entity.username else "لا يوجد"
                    first_name = user_entity.first_name or "لا يوجد"
                except:
                    username = "غير متاح"
                    first_name = "غير متاح"
                
                users_data.append({
                    "user_id": user_id_from_key,
                    "username": username,
                    "first_name": first_name,
                    "coins": round(user_info.get("coins", 0), 2) if user_info else 0.0,
                    "id": user_info.get("id", 0) if user_info else 0
                })
            
            backup_data["users"] = users_data
            backup_data["total_users"] = total_users
            
            # جمع بيانات الدول
            if db.exists("countries"):
                backup_data["countries"] = db.get("countries")
            else:
                backup_data["countries"] = []
            
            # جمع بيانات الحسابات
            accounts_data = {}
            if db.exists("countries"):
                for country in db.get("countries"):
                    country_code = country['calling_code']
                    if db.exists(f"accounts_{country_code}"):
                        accounts_data[country_code] = db.get(f"accounts_{country_code}")
            
            backup_data["accounts"] = accounts_data
            
            # جمع بيانات الإعدادات الأخرى
            if db.exists("force"):
                backup_data["force_channels"] = db.get("force")
            else:
                backup_data["force_channels"] = []
            
            if db.exists("admins"):
                backup_data["admins"] = db.get("admins")
            else:
                backup_data["admins"] = [admin]
            
            if db.exists("bad_guys"):
                backup_data["banned_users"] = db.get("bad_guys")
            else:
                backup_data["banned_users"] = []
            
            if db.exists("trust_channel"):
                backup_data["trust_channel"] = db.get("trust_channel")
            
            if db.exists("rules_message"):
                backup_data["rules_message"] = db.get("rules_message")
            
            backup_data["maintenance"] = db.get("maintenance") if db.exists("maintenance") else False
            backup_data["backup_date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # حفظ البيانات في ملف JSON
            backup_file = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=4)
            
            # إرسال الملف
            with open(backup_file, 'rb') as f:
                await client.send_file(
                    user_id,
                    f,
                    caption=f"**📁︙ النسخة الاحتياطية للبوت**\n\n"
                           f"• تاريخ النسخة: {backup_data['backup_date']}\n"
                           f"• عدد المستخدمين: {total_users}\n"
                           f"• عدد الدول: {len(backup_data.get('countries', []))}\n"
                           f"• حالة الصيانة: {'مفعلة' if backup_data['maintenance'] else 'غير مفعلة'}\n\n"
                           f"**لرفع هذه النسخة:**\n"
                           f"1. احفظ الملف\n"
                           f"2. استخدم زر 'رفع ملف نسخة'\n"
                           f"3. أرسل الملف",
                    attributes=[DocumentAttributeFilename(file_name=backup_file)]
                )
            
            # حذف الملف المؤقت
            os.remove(backup_file)
            
            await event.edit(
                '**✅︙ تم إنشاء ملف النسخة الاحتياطية بنجاح**\n\n'
                '• تم إرسال ملف النسخة الاحتياطية\n'
                '• يمكنك حفظه واستخدامه لاحقاً\n'
                '• أو رفعه عن طريق زر "رفع ملف نسخة"',
                buttons=[
                    [Button.inline("⦉ رجوع ⬅️ ⦊", data="backup_system")]
                ]
            )
            
        except Exception as e:
            await event.edit(
                f'**❌︙ حدث خطأ أثناء إنشاء النسخة الاحتياطية**\n\n'
                f'• الخطأ: {str(e)}\n'
                f'• الرجاء المحاولة مرة أخرى',
                buttons=[
                    [Button.inline("⦉ رجوع ⬅️ ⦊", data="backup_system")]
                ]
            )

    @client.on(events.CallbackQuery(pattern=b'upload_backup'))
    async def upload_backup_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        await event.edit(
            '**📤︙ رفع ملف النسخة الاحتياطية**\n\n'
            '• الرجاء إرسال ملف النسخة الاحتياطية (JSON)\n'
            '• سيتم تطبيق الإعدادات من الملف\n'
            '• تأكد من صحة الملف قبل الرفع\n\n'
            '**تحذير:** هذا الإجراء سيقوم بتحديث إعدادات البوت الحالية!',
            buttons=[
                [Button.inline("⦉ إلغاء ⬅️ ⦊", data="backup_system")]
            ]
        )
        
        async with bot.conversation(event.chat_id) as conv:
            await conv.send_message("الرجاء إرسال ملف النسخة الاحتياطية الآن (JSON)...")
            
            try:
                # انتظار استلام الملف
                response = await conv.wait_event(events.NewMessage(incoming=True, from_users=user_id), timeout=60)
                
                if hasattr(response, 'document') and response.document:
                    # تنزيل الملف
                    backup_file = await response.download_media()
                    
                    # قراءة الملف
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        backup_data = json.load(f)
                    
                    # تطبيق البيانات من النسخة الاحتياطية
                    try:
                        # تحديث بيانات المستخدمين
                        if "users" in backup_data:
                            for user in backup_data["users"]:
                                db.set(f"user_{user['user_id']}", {
                                    "coins": round(float(user.get("coins", 0)), 2),
                                    "id": user.get("id", 0)
                                })
                        
                        # تحديث الدول
                        if "countries" in backup_data:
                            db.set("countries", backup_data["countries"])
                        
                        # تحديث الحسابات
                        if "accounts" in backup_data:
                            for country_code, accounts in backup_data["accounts"].items():
                                db.set(f"accounts_{country_code}", accounts)
                        
                        # تحديث قنوات الاشتراك الإجباري
                        if "force_channels" in backup_data:
                            db.set("force", backup_data["force_channels"])
                        
                        # تحديث الأدمن
                        if "admins" in backup_data:
                            db.set("admins", backup_data["admins"])
                        
                        # تحديث المحظورين
                        if "banned_users" in backup_data:
                            db.set("bad_guys", backup_data["banned_users"])
                        
                        # تحديث قناة الثقة
                        if "trust_channel" in backup_data:
                            db.set("trust_channel", backup_data["trust_channel"])
                        
                        # تحديث رسالة القوانين
                        if "rules_message" in backup_data:
                            db.set("rules_message", backup_data["rules_message"])
                        
                        # تحديث حالة الصيانة
                        if "maintenance" in backup_data:
                            db.set("maintenance", backup_data["maintenance"])
                        
                        # حذف الملف المؤقت
                        os.remove(backup_file)
                        
                        await conv.send_message(
                            f"**✅︙ تم تطبيق النسخة الاحتياطية بنجاح**\n\n"
                            f"• تاريخ النسخة: {backup_data.get('backup_date', 'غير معروف')}\n"
                            f"• عدد المستخدمين: {backup_data.get('total_users', 0)}\n"
                            f"• عدد الدول: {len(backup_data.get('countries', []))}\n"
                            f"• تم تحديث جميع الإعدادات"
                        )
                        
                    except Exception as e:
                        await conv.send_message(
                            f"**❌︙ حدث خطأ أثناء تطبيق النسخة الاحتياطية**\n\n"
                            f"• الخطأ: {str(e)}\n"
                            f"• قد تكون بعض البيانات لم يتم تحديثها"
                        )
                
                else:
                    await conv.send_message("❌ لم يتم إرسال ملف، الرجاء المحاولة مرة أخرى.")
                    
            except asyncio.TimeoutError:
                await conv.send_message("⏰ انتهى وقت الانتظار، الرجاء المحاولة مرة أخرى.")

    @client.on(events.CallbackQuery(pattern=b'backup_info'))
    async def backup_info_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        # حساب الإحصائيات
        total_users = len(db.keys('user_%'))
        countries_count = len(db.get("countries")) if db.exists("countries") else 0
        
        total_accounts = 0
        if db.exists("countries"):
            for country in db.get("countries"):
                country_code = country['calling_code']
                if db.exists(f"accounts_{country_code}"):
                    total_accounts += len(db.get(f"accounts_{country_code}"))
        
        force_channels = len(db.get("force")) if db.exists("force") else 0
        admins_count = len(db.get("admins")) if db.exists("admins") else 0
        banned_users = len(db.get("bad_guys")) if db.exists("bad_guys") else 0
        
        await event.edit(
            f'**📊︙ معلومات النسخة الاحتياطية الحالية**\n\n'
            f'👥 **المستخدمين:**\n'
            f'• إجمالي المستخدمين: {total_users}\n'
            f'• عدد الأدمن: {admins_count}\n'
            f'• عدد المحظورين: {banned_users}\n\n'
            f'🌍 **الدول والأرقام:**\n'
            f'• عدد الدول: {countries_count}\n'
            f'• إجمالي الأرقام: {total_accounts}\n\n'
            f'⚙️ **الإعدادات:**\n'
            f'• قنوات الإشتراك الإجباري: {force_channels}\n'
            f'• حالة الصيانة: {"✅ مفعلة" if db.get("maintenance") else "❌ غير مفعلة"}\n\n'
            f'📅 **آخر تحديث:**\n'
            f'• {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            buttons=[
                [Button.inline("⦉ رجوع ⬅️ ⦊", data="backup_system")]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'statistics'))
    async def statistics_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        await event.answer(' - قسم الاحصائيات 📊', alert=False)
        await event.edit(
            '**📊︙ قسم الاحصائيات**\n\n'
            '• هنا يمكنك عرض إحصائيات البوت\n'
            '• وتنزيل ملف يحتوي على معلومات المستخدمين\n\n'
            '**اختر الإجراء المطلوب:**',
            buttons=[
                [
                    Button.inline("📈 عرض الاحصائيات", data="show_stats"),
                    Button.inline("📥 تنزيل ملف المستخدمين", data="download_users_file")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'show_stats'))
    async def show_stats_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        # حساب الإحصائيات
        total_users = len(db.keys('user_%'))
        countries_count = len(db.get("countries")) if db.exists("countries") else 0
        
        total_accounts = 0
        if db.exists("countries"):
            for country in db.get("countries"):
                country_code = country['calling_code']
                if db.exists(f"accounts_{country_code}"):
                    total_accounts += len(db.get(f"accounts_{country_code}"))
        
        force_channels = len(db.get("force")) if db.exists("force") else 0
        admins_count = len(db.get("admins")) if db.exists("admins") else 0
        banned_users = len(db.get("bad_guys")) if db.exists("bad_guys") else 0
        
        # حساب إجمالي الرصيد
        total_coins = 0.0
        users_keys = db.keys('user_%')
        for key in users_keys:
            if isinstance(key, tuple):
                key = key[0]  # إذا كان المفتاح tuple، خذ العنصر الأول
            
            user_info = db.get(key)
            if user_info:
                total_coins += round(float(user_info.get("coins", 0)), 2)
        
        await event.edit(
            f'**📊︙ إحصائيات البوت**\n\n'
            f'👥 **المستخدمين:**\n'
            f'• إجمالي المستخدمين: {total_users}\n'
            f'• عدد الأدمن: {admins_count}\n'
            f'• عدد المحظورين: {banned_users}\n\n'
            f'💰 **الرصيد:**\n'
            f'• إجمالي الرصيد في البوت: {total_coins:.2f} $\n\n'  # تغيير من "عملات" إلى "$"
            f'🌍 **الدول والأرقام:**\n'
            f'• عدد الدول: {countries_count}\n'
            f'• إجمالي الأرقام: {total_accounts}\n\n'
            f'⚙️ **الإعدادات:**\n'
            f'• قنوات الإشتراك الإجباري: {force_channels}\n'
            f'• حالة الصيانة: {"✅ مفعلة" if db.get("maintenance") else "❌ غير مفعلة"}\n\n'
            f'📅 **التاريخ:**\n'
            f'• {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            buttons=[
                [Button.inline("⦉ رجوع ⬅️ ⦊", data="statistics")]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'download_users_file'))
    async def download_users_file_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        await event.answer("📥 جاري إنشاء ملف المستخدمين...", alert=False)
        
        try:
            # جمع بيانات المستخدمين
            users_data = []
            users_keys = db.keys('user_%')
            
            for key in users_keys:
                if isinstance(key, tuple):
                    key = key[0]  # إذا كان المفتاح tuple، خذ العنصر الأول
                
                user_info = db.get(key)
                if not user_info:
                    continue
                    
                user_id_from_key = key.replace('user_', '')
                
                # محاولة الحصول على معلومات المستخدم من التليجرام
                try:
                    user_entity = await client.get_entity(int(user_id_from_key))
                    username = f"@{user_entity.username}" if user_entity.username else "لا يوجد"
                    first_name = user_entity.first_name or "لا يوجد"
                    last_name = user_entity.last_name or ""
                except:
                    username = "غير متاح"
                    first_name = "غير متاح"
                    last_name = ""
                
                # التحقق مما إذا كان المستخدم أدمن
                admins_list = db.get("admins") if db.exists("admins") else []
                is_admin = "نعم" if int(user_id_from_key) in admins_list else "لا"
                
                # التحقق مما إذا كان المستخدم محظور
                banned_list = db.get("bad_guys") if db.exists("bad_guys") else []
                is_banned = "نعم" if user_id_from_key in banned_list else "لا"
                
                users_data.append({
                    "id": user_id_from_key,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "coins": round(float(user_info.get("coins", 0)), 2),
                    "is_admin": is_admin,
                    "is_banned": is_banned
                })
            
            # إنشاء ملف CSV
            csv_file = f"users_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = ['id', 'username', 'first_name', 'last_name', 'coins', 'is_admin', 'is_banned']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                writer.writeheader()
                for user in users_data:
                    writer.writerow(user)
            
            # إنشاء ملف نصي أيضا
            txt_file = f"users_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"📊 ملف مستخدمي البوت\n")
                f.write(f"📅 تاريخ الإنشاء: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"👥 إجمالي المستخدمين: {len(users_data)}\n")
                f.write("="*50 + "\n\n")
                
                for i, user in enumerate(users_data, 1):
                    f.write(f"👤 المستخدم رقم {i}:\n")
                    f.write(f"🆔 الأيدي: {user['id']}\n")
                    f.write(f"👤 الاسم: {user['first_name']} {user['last_name']}\n")
                    f.write(f"📌 المعرف: {user['username']}\n")
                    f.write(f"💰 الرصيد: {user['coins']:.2f} $\n")  # تغيير من "عملات" إلى "$"
                    f.write(f"👑 أدمن: {user['is_admin']}\n")
                    f.write(f"🚫 محظور: {user['is_banned']}\n")
                    f.write("-"*30 + "\n")
            
            # إرسال الملفين
            with open(csv_file, 'rb') as f:
                await client.send_file(
                    user_id,
                    f,
                    caption=f"**📊︙ ملف مستخدمي البوت (CSV)**\n\n"
                           f"• عدد المستخدمين: {len(users_data)}\n"
                           f"• التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                           f"**يمكنك فتح هذا الملف بـ:**\n"
                           f"• Excel\n• Google Sheets\n• أي برنامج جداول بيانات",
                    attributes=[DocumentAttributeFilename(file_name=csv_file)]
                )
            
            with open(txt_file, 'rb') as f:
                await client.send_file(
                    user_id,
                    f,
                    caption=f"**📄︙ ملف مستخدمي البوت (نصي)**\n\n"
                           f"• نفس البيانات لكن بصيغة نصية\n"
                           f"• أسهل للقراءة",
                    attributes=[DocumentAttributeFilename(file_name=txt_file)]
                )
            
            # حذف الملفات المؤقتة
            os.remove(csv_file)
            os.remove(txt_file)
            
            await event.edit(
                f'**✅︙ تم إنشاء ملفات المستخدمين بنجاح**\n\n'
                f'• تم إرسال ملفين:\n'
                f'1. ملف CSV للاستخدام في الجداول\n'
                f'2. ملف نصي للقراءة السهلة\n\n'
                f'• إجمالي المستخدمين: {len(users_data)}',
                buttons=[
                    [Button.inline("⦉ رجوع ⬅️ ⦊", data="statistics")]
                ]
            )
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error in download_users_file: {error_details}")
            
            await event.edit(
                f'**❌︙ حدث خطأ أثناء إنشاء ملف المستخدمين**\n\n'
                f'• الخطأ: {str(e)}\n'
                f'• نوع الخطأ: {type(e).__name__}\n'
                f'• الرجاء المحاولة مرة أخرى',
                buttons=[
                    [Button.inline("⦉ رجوع ⬅️ ⦊", data="statistics")]
                ]
            )

    @client.on(events.CallbackQuery(pattern=b'maintenance_system'))
    async def maintenance_system_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        maintenance_status = db.get("maintenance")
        status_text = "🟢 مفعلة" if maintenance_status else "🔴 غير مفعلة"
        
        await event.answer(' - قسم نظام الصيانة 🔧', alert=False)
        await event.edit(
            f'**🔧︙ نظام الصيانة**\n\n'
            f'• حالة الصيانة الحالية: **{status_text}**\n\n'
            f'**اختر الإجراء المطلوب:**',
            buttons=[
                [
                    Button.inline("✅ تشغيل الصيانة", data="enable_maintenance"),
                    Button.inline("❌ إيقاف الصيانة", data="disable_maintenance")
                ],
                [
                    Button.inline("📊 عرض الحالة", data="show_maintenance_status")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'enable_maintenance'))
    async def enable_maintenance_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        db.set("maintenance", True)
        
        # إرسال إشعار للمسؤولين
        admins = db.get("admins")
        for admin_id in admins:
            try:
                await client.send_message(
                    admin_id,
                    f"🔧 **تم تفعيل وضع الصيانة**\n\n"
                    f"• المستخدم: {user_id}\n"
                    f"• التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"• البوت الآن في وضع الصيانة\n"
                    f"• فقط المسؤولون يمكنهم استخدام البوت"
                )
            except:
                pass
        
        await event.answer("✅ تم تفعيل وضع الصيانة بنجاح", alert=True)
        await event.edit(
            '**🔧︙ تم تفعيل وضع الصيانة بنجاح**\n\n'
            '• البوت الآن في وضع الصيانة\n'
            '• فقط المسؤولون يمكنهم استخدام البوت\n'
            '• المستخدمون العاديون سيظهر لهم رسالة الصيانة',
            buttons=[
                [Button.inline("⦉ رجوع ⬅️ ⦊", data="maintenance_system")]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'disable_maintenance'))
    async def disable_maintenance_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        db.set("maintenance", False)
        
        # إرسال إشعار للمسؤولين
        admins = db.get("admins")
        for admin_id in admins:
            try:
                await client.send_message(
                    admin_id,
                    f"🟢 **تم إيقاف وضع الصيانة**\n\n"
                    f"• المستخدم: {user_id}\n"
                    f"• التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"• البوت يعمل بشكل طبيعي الآن\n"
                    f"• جميع المستخدمين يمكنهم استخدام البوت"
                )
            except:
                pass
        
        await event.answer("✅ تم إيقاف وضع الصيانة بنجاح", alert=True)
        await event.edit(
            '**🟢︙ تم إيقاف وضع الصيانة بنجاح**\n\n'
            '• البوت يعمل بشكل طبيعي الآن\n'
            '• جميع المستخدمين يمكنهم استخدام البوت\n'
            '• تم إلغاء رسالة الصيانة',
            buttons=[
                [Button.inline("⦉ رجوع ⬅️ ⦊", data="maintenance_system")]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'show_maintenance_status'))
    async def show_maintenance_status_handler(event):
        user_id = event.chat_id
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
        
        maintenance_status = db.get("maintenance")
        status_text = "✅ مفعلة" if maintenance_status else "❌ غير مفعلة"
        status_emoji = "🛠️" if maintenance_status else "🟢"
        
        await event.edit(
            f'**📊︙ حالة الصيانة الحالية**\n\n'
            f'{status_emoji} **الحالة:** {status_text}\n\n'
            f'**التأثير:**\n'
            f'• عندما تكون الصيانة **مفعلة**:\n'
            f'  - فقط المسؤولون يمكنهم استخدام البوت\n'
            f'  - المستخدمون العاديون يرون رسالة الصيانة\n\n'
            f'• عندما تكون الصيانة **غير مفعلة**:\n'
            f'  - جميع المستخدمين يمكنهم استخدام البوت\n'
            f'  - البوت يعمل بشكل طبيعي',
            buttons=[
                [Button.inline("⦉ رجوع ⬅️ ⦊", data="maintenance_system")]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'check_subscription'))
    async def check_subscription_handler(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.edit(msgs['MAINTENANCE_MESSAGE'])
                return
        
        force = db.get("force") if db.exists("force") else []

        if not force:
            await event.answer("لا توجد قنوات اشتراك إجباري", alert=True)
            return

        not_joined = []
        for channel in force:
            try:
                await client(GetParticipantRequest(
                    channel=channel,
                    participant=user_id
                ))
            except:
                not_joined.append(channel)

        if not_joined:
            channel_text = "\n".join([f"• @{channel}" for channel in not_joined])
            keyboard = [
                [Button.url(f"اشترك في @{channel}", f"https://t.me/{channel}")] for channel in not_joined
            ]
            keyboard.append([Button.inline("✅ تحقق من الاشتراك", data="check_subscription")])
            await event.edit(
                f"**❌ لم تشترك بعد في القنوات التالية:**\n\n{channel_text}\n\n"
                f"**• الرجاء الاشتراك ثم اضغط على زر التحقق**",
                buttons=keyboard
            )
        else:
            # Start the bot for the user
            user_info = db.get(f"user_{user_id}")
            coins = user_info["coins"] if user_info else 0
            
            # عرض الرصيد مع تنسيق عشري ثابت
            if isinstance(coins, (int, float)):
                display_coins = round(float(coins), 2)
            else:
                display_coins = 0.0
            
            buttons = [
                [
                    Button.inline("- شراء رقم ✅ .", data="buy"),
                ],
                [
                    Button.inline("- شحن رصيد 💰.", data="contact_admin"),
                    Button.inline("- تحويل رصيد ♻️.", data="transfer"),
                ],
                [
                    Button.inline("- قناة البوت 📢.", data="bot_channel"),
                    Button.inline("- القوانين 🔐.", data="liscgh"),
                ],
                [
                    Button.inline("- الهديه اليوميه 🎁.", data="daily_gift"),
                ]
            ]
            await event.edit(msgs['START_MESSAGE'].format(event.chat_id, display_coins), buttons=buttons)

    # Callback handlers
    @client.on(events.CallbackQuery(pattern=b'ajxjao'))
    async def numgpv_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer(' - مرحباً بك عزيزي في قسم الارقام ☎️ .')
        await event.edit(
            '** 🚀︙مرحبا بك عزيزي بقسم الارقام ** \n ✅︙يمكنك التحكم في ارقامك بكل سهوله \n 👤︙الارقام يتم تحديثها تلقائي \n **✳️︙ماذا تنتظر اذهب الان للتحكم في الارقام **',
            buttons=[
                [
                    Button.inline("- عدد ارقام البوت 🚀.", data="all_of_number")
                ],
                [
                    Button.inline("- اضافة دوله 🌎.", data="add_country"),
                    Button.inline("- حذف دوله ❌.", data="del_country")
                ],
                [
                    Button.inline("- اضافة رقم ✅.", data="add"),
                    Button.inline("- حذف رقم ⛔.", data="del_account")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'ajxkho'))
    async def nuupv_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer(' - مرحباً بك عزيزي في قسم االاشتراك الاجباري 〽️️ .')
        await event.edit(
            '** 〽️︙اختر ماذا تريده من قسم الاشتراك الاجباري **',
            buttons=[
                [
                    Button.inline("- اضافة قناه 🌟.", data="add_force"),
                    Button.inline("- حذف قناه ⛔.", data="del_force")
                ],
                [
                    Button.inline("- عرض القنوات 📋", data="show_force_channels")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'aksgl'))
    async def nuupv_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer(' - مرحباً بك عزيزي في قسم الادمنيه 👨‍✈️️ .')
        await event.edit(
            '** 👨‍✈️️︙اختر ماذا تريده من قسم الادمنيه **',
            buttons=[
                [
                    Button.inline("- اضافة ادمن 🤍.", data="add_admin"),
                    Button.inline("- حذف ادمن ✖️.", data="del_admin")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'ajkofgl'))
    async def nuupv_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer(' - مرحباً بك عزيزي في قسم البيع 💰 .')
        await event.edit(
            '**💰︙اختر ماذا تريده من قسم البيع **',
            buttons=[
                [
                    Button.inline("- تغيير سعر بيع ✅.", data="change_sell_price")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'ajkcoingl'))
    async def nuupv_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer(' - مرحباً بك عزيزي في قسم النقاط .')
        await event.edit(
            '**💰︙اختر ماذا تريده من قسم النقاط **',
            buttons=[
                [
                    Button.inline("- اضافة رصيد 💰.", data="add_coins"),
                    Button.inline("- خصم رصيد ✨.", data="del_coins")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'bbvjls'))
    async def nuupv_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer(' - مرحباً بك عزيزي في قسم الحظر .')
        await event.edit(
            '**🚫︙اختر ماذا تريده من قسم الحظر **',
            buttons=[
                [
                    Button.inline("- حظر شخص 🚫.", data="ban"),
                    Button.inline("- الغاء حظر ✅.", data="unban")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="admin_panel")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'contact_admin'))
    async def contact_admin_handler(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.edit(
            "**📞︙اختر طريقة التواصل:**\n\n"
            "• اضغط على الزر المناسب للتواصل مع المسؤولين",
            buttons=[
                [
                    Button.url("👑 مالك", "https://t.me/t2_1y"),
                    Button.url("👨‍✈️ ادمن", "https://t.me/M2_OG")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="main")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'bot_channel'))
    async def bot_channel_handler(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer("يتم تحويلك لقناة البوت...", alert=False)
        await event.edit(
            "**📢︙قناة البوت الرسمية:**\n\n"
            "• اضغط على الزر أدناه للذهاب إلى قناة البوت",
            buttons=[
                [
                    Button.url("📢 قناة البوت", "https://t.me/GM_TT0")
                ],
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="main")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'daily_gift'))
    async def daily_gift_handler(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        await event.answer("يوجد صيانة في قسم الهدية اليومية ⚠️", alert=True)
        await event.edit(
            "**🎁︙الهدية اليومية:**\n\n"
            "• عذراً، يوجد صيانة في قسم الهدية اليومية حالياً ⚠️\n"
            "• سيتم إعادة تفعيله قريباً بإذن الله",
            buttons=[
                [
                    Button.inline("⦉ رجوع ⬅️ ⦊", data="main")
                ]
            ]
        )

    @client.on(events.CallbackQuery(pattern=b'liscgh'))
    async def rules_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ البوت تحت الصيانة", alert=True)
                return
        
        if db.exists("rules_message"):
            rules_message = db.get("rules_message")
        else:
            rules_message = "مرحباً عزيزي، يجب عليك الالتزام بالقوانين التالية:\n\n1. لا تنشر محتوى غير لائق.\n2. لا تستخدم البوت لأغراض غير قانونية.\n3. يجب عليك التحلي بالصبر والاحترام في التعامل مع الآخرين.\n4. في حالة وجود مشكلة، تواصل مع المسؤولين."

        await event.edit(rules_message, buttons=[Button.inline("رجوع", data="main")])

    @client.on(events.CallbackQuery(pattern=b'edit_rules'))
    async def edit_rules_button(event):
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
        
        if user_id != admin and user_id not in db.get("admins"):
            await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
            return
            
        async with bot.conversation(event.chat_id) as conv:
            await conv.send_message("الرجاء إرسال رسالة القوانين الجديدة.")
            response = await conv.get_response()

            db.set("rules_message", response.text)
            await conv.send_message("تم تحديث رسالة القوانين بنجاح.")

    @client.on(events.CallbackQuery())
    async def callback_handler(event):
        data = event.data.decode('utf-8')
        user_id = event.chat_id
        
        # التحقق من حالة الصيانة قبل أي معالجة
        if db.get("maintenance"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.edit(msgs['MAINTENANCE_MESSAGE'])
                return
        
        bans = db.get('bad_guys') if db.exists('bad_guys') else []

        # Check force subscription for users (not admins)
        if user_id != admin and user_id not in db.get("admins"):
            force = db.get("force") if db.exists("force") else []
            if force:
                not_joined = []
                for channel in force:
                    try:
                        await client(GetParticipantRequest(
                            channel=channel,
                            participant=user_id
                        ))
                    except:
                        not_joined.append(channel)

                if not_joined:
                    channel_text = "\n".join([f"• @{channel}" for channel in not_joined])
                    keyboard = [
                        [Button.url(f"اشترك في @{channel}", f"https://t.me/{channel}")] for channel in not_joined
                    ]
                    keyboard.append([Button.inline("✅ تحقق من الاشتراك", data="check_subscription")])
                    await event.edit(
                        f"**⚠️︙عذراً عزيزي يجب عليك الاشتراك في القنوات التالية أولاً:**\n\n{channel_text}\n\n"
                        f"**• بعد الاشتراك اضغط على زر التحقق**",
                        buttons=keyboard
                    )
                    return

        if user_id in bans:
            return

        # Handle all callback data patterns
        if data == "admin_panel":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            keyboard = [
                [
                    Button.inline("- اعدادات الارقام 🚀 .", data="ajxjao"),
                ],
                [
                    Button.inline("- الاشتراك الاجباري 〽️.", data="ajxkho"),
                    Button.inline("- قسم الادمنيه 👨‍✈️.", data="aksgl"),
                ],
                [
                    Button.inline("- قسم البيع 💰 .", data="ajkofgl"),
                ],
                [
                    Button.inline("- قسم الرصيد 🤍.", data="ajkcoingl"),
                    Button.inline("- قسم الحظر 🚫.", data="bbvjls"),
                ],
                [
                    Button.inline("- قناة اثباتات التسليم 🖤 .", data="set_trust_channel"),
                ],
                [
                    Button.inline("- الاحصائيات 📊 .", data="statistics"),  # زر جديد للإحصائيات
                ],
                [
                    Button.inline("- النسخ الاحتياطي 📁 .", data="backup_system"),  # زر جديد للنسخ الاحتياطي
                ],
                [
                    Button.inline("- نظام الصيانة 🔧 .", data="maintenance_system"),
                ]
            ]
            await event.edit(msgs['ADMIN_MESSAGE'], buttons=keyboard)
            return

        elif data == "show_force_channels":
            force = db.get("force") if db.exists("force") else []
            if not force:
                await event.answer("لا توجد قنوات اشتراك إجباري", alert=True)
                return

            channels_text = "**📋︙قائمة قنوات الاشتراك الإجباري:**\n\n"
            for i, channel in enumerate(force, 1):
                channels_text += f"{i}. @{channel}\n"

            await event.edit(
                channels_text,
                buttons=[
                    [Button.inline("⦉ رجوع ⬅️ ⦊", data="ajxkho")]
                ]
            )
            return

        elif data == "change_sell_price":
            countries = db.get("countries")
            buttons = []
            row = []
            for code in countries:
                calling_code = code['calling_code']
                name = code['name']
                price = code['sell_price']
                if len(row) < 2:
                    row.append(Button.inline(text=f"{name} : {float(price):.2f} $", data=f"chs_{calling_code}_{name}_{price}"))  # تغيير من "عملات" إلى "$"
                else:
                    buttons.append(row)
                    row = [Button.inline(text=f"{name} : {float(price):.2f} $", data=f"chs_{calling_code}_{name}_{price}")]  # تغيير من "عملات" إلى "$"
            if row:
                buttons.append(row)

            buttons.append([Button.inline(text="رجوع ↩️", data="admin_panel")])
            await event.edit("- اختر الدولة التي تريد تغيير سعرها\n- سعر البيع هو السعر بجانب اسم الدولة", parse_mode='markdown', buttons=buttons)
            return

        elif data.startswith("chs_"):
            calling_code = data.split('_')[1]
            name = data.split('_')[2]
            old_price = data.split('_')[3]
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل الان سعر البيع الجديد الذي تريد تعيينه لدولة {name}")
                ch = await x.get_response()
                try:
                    new_price = round(float(ch.text), 2)
                except:
                    await x.send_message(f"- برجاء ارسل العدد ارقام او ارقام عشرية ")
                    return
                countries = db.get("countries")
                for i in countries:
                    if calling_code == i['calling_code']:
                        i['sell_price'] = new_price
                        db.set("countries", countries)
                        await x.send_message(f"- تم تغيير سعر دولة {name} الي {new_price:.2f} $")  # تغيير من "عملات" إلى "$"
                        return
                await x.send_message(f"- حدث خطأ اثناء تغيير سعر الخدمة ❌")

        elif data == "add_force":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل الان معرف او رابط قناة الاشتراك الاجباري.")
                ch = await x.get_response()
                channel = ch.text.replace('https://t.me/', '').replace('@', '').replace(" ", "")
                force = db.get("force") if db.exists("force") else []
                if channel in force:
                    await x.send_message(f"- هذه القناة ضمن قنوات الاشتراك الاجباري بالفعل!.")
                    return
                force.append(channel)
                db.set("force", force)
                await x.send_message(f"- تم حفظ قناة الاشتراك الاجباري بنجاح.")
                return

        elif data == "del_force":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                force = db.get("force") if db.exists("force") else []
                if not force:
                    await x.send_message(f"- لا توجد قنوات اشتراك اجباري لحذفها.")
                    return

                await x.send_message(f"- اختر القناة التي تريد حذفها:\n\n" + "\n".join([f"{i+1}. @{channel}" for i, channel in enumerate(force)]))
                ch = await x.get_response()
                try:
                    index = int(ch.text) - 1
                    if 0 <= index < len(force):
                        channel = force[index]
                        force.remove(channel)
                        db.set("force", force)
                        await x.send_message(f"- تم حذف قناة @{channel} من الاشتراك الاجباري بنجاح.")
                    else:
                        await x.send_message(f"- رقم غير صحيح.")
                except:
                    await x.send_message(f"- ارسل رقم القناة بشكل صحيح.")
                return

        elif data == "transfer":
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(msgs['TRANSFER_MESSAGE'])
                iii = await x.get_response()
                try:
                    id = int(iii.text)
                except:
                    return await x.send_message("- ارسل ايدي المستخدم بشكل صحيح!.")
                if user_id == id:
                    return await x.send_message("- لا يمكنك تحويل الرصيد لنفسك!.")
                if not db.exists(f"user_{id}"):
                    return await x.send_message("- هذا المستخدم غير موجود ضمن بياناتنا!.")
                less = db.get("transfer_minimum") if db.exists("transfer_minimum") else 5
                await x.send_message(f"**• حسنا قم بإرسال الرصيد الذي تود تحويله ♻**\n\n- أدنى حد للتحويل {less:.2f} $")  # تغيير من "عملات" إلى "$"
                cou = await x.get_response()
                try:
                    count = round(float(cou.text), 2)
                except:
                    return await x.send_message("- ارسل الرصيد بشكل صحيح في صورة ارقام او ارقام عشرية!.")
                info = db.get(f"user_{user_id}")
                transfer_fee = round(count * 0.02, 2)
                total_deduct = round(count + transfer_fee, 2)
                
                # التحقق من الرصيد بدقة
                user_balance = round(float(info.get('coins', 0)), 2)
                if user_balance < total_deduct:
                    return await x.send_message(f"- رصيد غير كافٍ لتحويل هذا القدر من الرصيد!.\n- رصيدك: {user_balance:.2f} $\n- المبلغ المطلوب: {total_deduct:.2f} $")
                
                if less > count:
                    return await x.send_message(f"- الحد الادني لتحويل الرصيد هو {less:.2f} $!.")  # تغيير من "عملات" إلى "$"
                
                # خصم المبلغ
                info['coins'] = round(user_balance - total_deduct, 2)
                db.set(f"user_{user_id}", info)
                
                # إضافة المبلغ للمستلم
                acc = db.get(f"user_{id}")
                receiver_balance = round(float(acc.get('coins', 0)), 2)
                acc['coins'] = round(receiver_balance + count, 2)
                db.set(f"user_{id}", acc)
                
                await client.send_message(id, f"**- تم استلام مبلغ من الرصيد 📥**\n\n- قدره : {count:.2f} $\n- من : `{user_id}`")  # تغيير من "عملات" إلى "$"
                await x.send_message(f"**- تم ارسال مبلغ من الرصيد 📤**\n\n- قدره : {count:.2f} $\n- الي : `{id}`\n- عمولة التحويل: {transfer_fee:.2f} $\n- رصيدك الجديد: {info['coins']:.2f} $")  # تغيير من "عملات" إلى "$"
                await client.send_message(admin, f"**• تمت عملية تحويل رصيد ♻️**\n\n- من : `{user_id}`\n- إلي : `{id}`\n- المبلغ : {count:.2f} $\n- عمولة التحويل : {transfer_fee:.2f} $\n- الرصيد قبل: {user_balance:.2f} $\n- الرصيد بعد: {info['coins']:.2f} $")  # تغيير من "عملات" إلى "$"

        elif data == "add_coins":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل الان ايدي الشخص الذي تريد اضافة رصيد له.")
                id_msg = await x.get_response()
                try:
                    target_id = int(id_msg.text)
                except:
                    await x.send_message(f"- ارسل ايدي المستخدم بشكل صحيح.")
                    return
                    
                if not db.exists(f"user_{target_id}"):
                    await x.send_message(f"- هذا المستخدم لم ينضم الي البوت بعد.")
                    return
                    
                info = db.get(f"user_{target_id}")
                await x.send_message(f"- المستخدم : {target_id}\n- رصيده : {round(float(info.get('coins', 0)), 2):.2f} $\n\n- ارسل الان عدد الرصيد الذي تريد اضافته المستخدم")  # تغيير من "عملات" إلى "$"
                count_msg = await x.get_response()
                try:
                    add_amount = round(float(count_msg.text), 2)
                except:
                    await x.send_message(f"- ارسل عدد الرصيد ارقام او ارقام عشرية فقط.")
                    return
                    
                current_balance = round(float(info.get('coins', 0)), 2)
                info['coins'] = round(current_balance + add_amount, 2)
                db.set(f"user_{target_id}", info)
                await x.send_message(f"- تم اضافة الرصيد بنجاح.✅\n\n- رصيده القديم : {current_balance:.2f} $\n- رصيده الجديد : {info['coins']:.2f} $")  # تغيير من "عملات" إلى "$"
                message = f"- تم اضافة {add_amount:.2f} $ الي رصيدك. ✅\n\n- رصيدك القديم : {current_balance:.2f} $\n- رصيدك الحالي : {info['coins']:.2f} $"  # تغيير من "عملات" إلى "$"
                await client.send_message(target_id, message)
                return

        elif data == "del_coins":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل الان ايدي الشخص الذي تريد خصم رصيد منه.")
                id_msg = await x.get_response()
                try:
                    target_id = int(id_msg.text)
                except:
                    await x.send_message(f"- ارسل ايدي المستخدم بشكل صحيح.")
                    return
                    
                if not db.exists(f"user_{target_id}"):
                    await x.send_message(f"- هذا المستخدم لم ينضم الي البوت بعد.")
                    return
                    
                info = db.get(f"user_{target_id}")
                await x.send_message(f"- المستخدم : {target_id}\n- رصيده : {round(float(info.get('coins', 0)), 2):.2f} $\n\n- ارسل الان عدد الرصيد الذي تريد خصمه من المستخدم")  # تغيير من "عملات" إلى "$"
                count_msg = await x.get_response()
                try:
                    deduct_amount = round(float(count_msg.text), 2)
                except:
                    await x.send_message(f"- ارسل عدد الرصيد ارقام او ارقام عشرية فقط.")
                    return
                    
                current_balance = round(float(info.get('coins', 0)), 2)
                if current_balance < deduct_amount:
                    await x.send_message(f"- رصيد المستخدم لا يكفي للخصم!\n- رصيده: {current_balance:.2f} $\n- المبلغ المطلوب: {deduct_amount:.2f} $")
                    return
                    
                info['coins'] = round(current_balance - deduct_amount, 2)
                db.set(f"user_{target_id}", info)
                await x.send_message(f"- تم خصم الرصيد بنجاح.\n- رصيده القديم: {current_balance:.2f} $\n- رصيده الجديد: {info['coins']:.2f} $")  # تغيير من "عملات" إلى "$"
                return

        elif data == "ban":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل الان ايدي الشخص الذي تريد حظره من استخدام البوت.")
                id_msg = await x.get_response()
                try:
                    target_id = int(id_msg.text)
                except:
                    await x.send_message(f"- ارسل ايدي المستخدم بشكل صحيح.")
                    return
                    
                bans = db.get('bad_guys') if db.exists('bad_guys') else []
                if id_msg.text in bans:
                    await x.send_message(f"- هذا المستخدم محظور من البوت بالفعل!.")
                    return
                    
                bans.append(id_msg.text)
                db.set("bad_guys", bans)
                await x.send_message(f"- تم حظر المستخدم من إستخدام البوت.")
                return

        elif data == "unban":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل الان ايدي الشخص الذي تريد رفع حظره من استخدام البوت.")
                id_msg = await x.get_response()
                try:
                    target_id = int(id_msg.text)
                except:
                    await x.send_message(f"- ارسل ايدي المستخدم بشكل صحيح.")
                    return
                    
                bans = db.get('bad_guys') if db.exists('bad_guys') else []
                if id_msg.text not in bans:
                    await x.send_message(f"- هذا المستخدم غير محظور من البوت بالفعل!.")
                    return
                    
                bans.remove(id_msg.text)
                db.set("bad_guys", bans)
                await x.send_message(f"- تم رفع حظر المستخدم من إستخدام البوت.")
                return

        elif data == "all_of_number":
            countries = db.get("countries")
            count = 0
            keys = db.keys("accounts_%")
            for i in keys:
                if isinstance(i, tuple):
                    i = i[0]
                count += len(db.get(i))

            return await event.answer(f"- إجمالي ارقام البوت المسجلة : {count}.", alert=True)

        elif data == "main":
            user_info = db.get(f"user_{user_id}")
            coins = user_info["coins"] if user_info else 0
            
            # عرض الرصيد مع تنسيق عشري ثابت
            if isinstance(coins, (int, float)):
                display_coins = round(float(coins), 2)
            else:
                display_coins = 0.0
            
            buttons = [
                [
                    Button.inline("- شراء رقم ✅ .", data="buy"),
                ],
                [
                    Button.inline("- شحن رصيد 💰.", data="contact_admin"),
                    Button.inline("- تحويل رصيد ♻️.", data="transfer"),
                ],
                [
                    Button.inline("- قناة البوت 📢.", data="bot_channel"),
                    Button.inline("- القوانين 🔐.", data="liscgh"),
                ],
                [
                    Button.inline("- الهديه اليوميه 🎁.", data="daily_gift"),
                ]
            ]
            await event.edit(msgs['START_MESSAGE'].format(event.chat_id, display_coins), parse_mode='markdown', buttons=buttons)
            return

        elif data == "admin_panel":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            keyboard = [
                [
                    Button.inline("- اعدادات الارقام 🚀 .", data="ajxjao"),
                ],
                [
                    Button.inline("- الاشتراك الاجباري 〽️.", data="ajxkho"),
                    Button.inline("- قسم الادمنيه 👨‍✈️.", data="aksgl"),
                ],
                [
                    Button.inline("- قسم البيع 💰 .", data="ajkofgl"),
                ],
                [
                    Button.inline("- قسم الرصيد 🤍.", data="ajkcoingl"),
                    Button.inline("- قسم الحظر 🚫.", data="bbvjls"),
                ],
                [
                    Button.inline("- قناة اثباتات التسليم 🖤 .", data="set_trust_channel"),
                ],
                [
                    Button.inline("- الاحصائيات 📊 .", data="statistics"),  # زر جديد للإحصائيات
                ],
                [
                    Button.inline("- النسخ الاحتياطي 📁 .", data="backup_system"),  # زر جديد للنسخ الاحتياطي
                ],
                [
                    Button.inline("- نظام الصيانة 🔧 .", data="maintenance_system"),
                ]
            ]
            await event.edit(msgs['ADMIN_MESSAGE'], buttons=keyboard)
            return

        elif data == "buy" or data == "back":
            countries = db.get("countries")
            buttons = []
            row = []
            for code in countries:
                calling_code = code['calling_code']
                name = code['name']
                price = code['price']
                if len(row) < 2:
                    row.append(Button.inline(text=f"{name} : {float(price):.2f} $", data=f"countries_{calling_code}_{name}_{price}"))  # تغيير من "عملات" إلى "$"
                else:
                    buttons.append(row)
                    row = [Button.inline(text=f"{name} : {float(price):.2f} $", data=f"countries_{calling_code}_{name}_{price}")]  # تغيير من "عملات" إلى "$"
            if row:
                buttons.append(row)

            buttons.append([Button.inline(text="رجوع ↩️", data="main")])
            await event.edit(msgs['COUNTRY_LIST'], parse_mode='markdown', buttons=buttons)
            return

        elif data == "del_account":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            countries = db.get("countries")
            buttons = []
            row = []
            for code in countries:
                calling_code = code['calling_code']
                name = code['name']
                price = code['price']
                if len(row) < 2:
                    row.append(Button.inline(text=f"{name} : {float(price):.2f} $", data=f"show_{calling_code}_{name}_{price}"))  # تغيير من "عملات" إلى "$"
                else:
                    buttons.append(row)
                    row = [Button.inline(text=f"{name} : {float(price):.2f} $", data=f"show_{calling_code}_{name}_{price}")]  # تغيير من "عملات" إلى "$"
            if row:
                buttons.append(row)

            buttons.append([Button.inline(text="رجوع ↩️", data="admin_panel")])
            await event.edit("- اختر الدولة التي تريد حذف رقم منها", parse_mode='markdown', buttons=buttons)
            return

        elif data.startswith("show_"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            calling_code = data.split('_')[1]
            name = data.split('_')[2]
            price = data.split('_')[3]
            accounts = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
            if accounts == []:
                return await event.answer("- لا توجد أي حسابات في هذه الدولة.", alert=True)
            text = ""
            buttons = [[Button.inline(f"{count}: +{i['phone_number']}", data=f"v:{i['phone_number']}:{calling_code}:{name}:{price}")] for count, i in enumerate(accounts, 1)]
            buttons.append([Button.inline("رجوع ↩️", data=f"del_account")])
            await event.edit(f"- اليك قائمة الحسابات المسجلة لدولة : {name}", parse_mode='markdown', buttons=buttons)
            return

        elif data.startswith("v:"):
            phone_number = data.split(':')[1]
            calling_code = data.split(':')[2]
            name = data.split(':')[3]
            price = data.split(':')[4]
            info = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
            for i in info:
                if i['phone_number'] == phone_number:
                    text = f"- الحساب : `+{i['phone_number']}`\n- كلمة السر : `{i['two-step']}`\n\n**• اختر من الازرار ما تود فعله بهذه الحساب**"
            keyboard = [
                [
                    Button.inline("الحصول علي الكود", data=f"get:{phone_number}:{calling_code}:{name}:{price}"),
                ],
                [
                    Button.inline(f"+{phone_number} | Delete ❌", data=f"del:{phone_number}:{calling_code}:{name}"),
                ],
                [
                    Button.inline("رجوع ↩️", data=f"show_{calling_code}_{name}_{price}")
                ]
            ]
            await event.edit(text, parse_mode='markdown', buttons=keyboard)
            return

        elif data.startswith("del:"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            phone_number = data.split(':')[1]
            calling_code = data.split(':')[2]
            name = data.split(':')[3]
            text = f"- الرقم : `+{phone_number}`\n\n**- هل انت متاكد من حذف الرقم ؟**"
            keyboard = [
                [
                    Button.inline("رجوع ↩️", data=f"v:{phone_number}:{calling_code}:{name}"),
                    Button.inline("حذف ❌", data=f"del_done:{phone_number}:{calling_code}:{name}")
                ]
            ]
            await event.edit(text, parse_mode='markdown', buttons=keyboard)
            return

        elif data.startswith("del_done:"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            phone_number = data.split(':')[1]
            calling_code = data.split(':')[2]
            name = data.split(':')[3]
            keyboard = [
                [
                    Button.inline("رجوع ↩️", data="admin_panel")
                ]
            ]

            info = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
            for i in info:
                if i['phone_number'] == phone_number:
                    info.remove(i)
                    db.set(f"accounts_{calling_code}", info)
                    await event.edit(f"- تم حذف الرقم `+{phone_number}` من قائمة الارقام المسجلة في دولة {name}✅", parse_mode='markdown', buttons=keyboard)
                    return
            await event.edit(f"- فشل حذف الرقم `+{phone_number}` من قائمة الارقام المسجلة في دولة {name} ❌", parse_mode='markdown', buttons=keyboard)
            return

        elif data == "add":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            countries = db.get("countries")
            buttons = []
            row = []
            for code in countries:
                calling_code = code['calling_code']
                name = code['name']
                price = code['price']
                if len(row) < 2:
                    row.append(Button.inline(text=f"{name} : {float(price):.2f} $", data=f"rig_{calling_code}_{name}_{price}"))  # تغيير من "عملات" إلى "$"
                else:
                    buttons.append(row)
                    row = [Button.inline(text=f"{name} : {float(price):.2f} $", data=f"rig_{calling_code}_{name}_{price}")]  # تغيير من "عملات" إلى "$"
            if row:
                buttons.append(row)

            buttons.append([Button.inline(text="رجوع ↩️", data="main")])
            await event.edit("- اختر الدولة التي تريد اضافة الرقم بها", parse_mode='markdown', buttons=buttons)
            return

        elif data.startswith("rig_"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            calling_code = data.split('_')[1]
            name = data.split('_')[2]
            price = data.split('_')[3]
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل الان رقم حساب التليجرام مع رمز النداء لاضافته الي قائمة حسابات دولة {name}")
                txt = await x.get_response()
                phone_number = txt.text.replace("+", "").replace(" ", "")
                app = TelegramClient(StringSession(), api_id=API_ID, api_hash=API_HASH)
                await app.connect()
                password = None
                try:
                    code = await app.send_code_request(phone_number)
                except (ApiIdInvalidError):
                    await x.send_message("ʏᴏᴜʀ **ᴀᴩɪ_ɪᴅ** ᴀɴᴅ **ᴀᴩɪ_ʜᴀsʜ** ᴄᴏᴍʙɪɴᴀᴛɪᴏɴ ᴅᴏᴇsɴ'ᴛ ᴍᴀᴛᴄʜ ᴡɪᴛʜ ᴛᴇʟᴇɢʀᴀᴍ ᴀᴩᴘs sʏsᴛᴇᴍ.")
                    return
                except (PhoneNumberInvalidError):
                    await x.send_message("ᴛʜᴇ **ᴩʜᴏɴᴇ_ɴᴜᴍʙᴇʀ** ʏᴏᴜ'ᴠᴇ sᴇɴᴛ ᴅᴏᴇsɴ'ᴛ ʙᴇʟᴏɴɢ ᴛᴏ ᴀɴʏ ᴛᴇʟᴇɢʀᴀᴍ ᴀᴄᴄᴏᴜɴᴛ.")
                    return
                await x.send_message("- تم ارسال كود التحقق الخاص بك علي حسابك علي تليجرام.\n\n- ارسل الكود بالتنسيق التالي : 1 2 3 4 5")
                txt = await x.get_response()
                code = txt.text.replace(" ", "")
                try:
                    await app.sign_in(phone_number, code, password=None)
                    string_session = app.session.save()
                    data = {"phone_number": phone_number, "two-step": "2010", "session": string_session}
                    accounts = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
                    accounts.append(data)
                    db.set(f"accounts_{calling_code}", accounts)
                    await x.send_message(f"- تم اضافة الحساب الي قائمة الحسابات لدولة {name}\n- عدد ارقام هذه الدولة : {len(accounts)}\n\n- الرقم جاهز الان للبيع ✅")
                    await app.disconnect()
                except (PhoneCodeInvalidError):
                    await x.send_message("ᴛʜᴇ ᴏᴛᴩ ʏᴏᴜ'ᴠᴇ sᴇɴᴛ ɪs **ᴡʀᴏɴɢ.**")
                    await app.disconnect()
                    return
                except (PhoneCodeExpiredError):
                    await x.send_message("ᴛʜᴇ ᴏᴛᴩ ʏᴏᴜ'ᴠᴇ sᴇɴᴛ ɪs **ᴇxᴩɪʀᴇᴅ.**")
                    await app.disconnect()
                    return
                except (SessionPasswordNeededError):
                    await x.send_message("- ارسل رمز التحقق بخطوتين الخاص بحسابك")
                    txt = await x.get_response()
                    password = txt.text
                    try:
                        await app.sign_in(password=password)
                        string_session = app.session.save()
                        data = {"phone_number": phone_number, "two-step": password, "session": string_session}
                        accounts = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
                        accounts.append(data)
                        db.set(f"accounts_{calling_code}", accounts)
                        await x.send_message(f"- تم اضافة الحساب الي قائمة الحسابات لدولة {name}\n- عدد ارقام هذه الدولة : {len(accounts)}\n\n- الرقم جاهز الان للبيع ✅")
                        await app.disconnect()
                    except (PasswordHashInvalidError):
                        await x.send_message("ᴛʜᴇ ᴩᴀssᴡᴏʀᴅ ʏᴏᴜ'ᴠᴇ sᴇɴᴛ ɪs ᴡʀᴏɴɢ.")
                        await app.disconnect()
                        return
            return

        elif data == 'zip_all':
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            folder_path = f"./database"
            zip_file_name = f"database.zip"
            zip_file_nam = f"database"
            try:
                shutil.make_archive(zip_file_nam, 'zip', folder_path)
                with open(zip_file_name, 'rb') as zip_file:
                    await client.send_file(user_id, zip_file, attributes=[DocumentAttributeFilename(file_name="database.zip")])
                os.remove(zip_file_name)
            except Exception as a:
                print(a)

        elif data.startswith("get:"):
            phone_number = data.split(':')[1]
            calling_code = data.split(':')[2]
            name = data.split(':')[3]
            price = data.split(':')[4]
            info = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
            keyboard = [
                [
                    Button.inline("رجوع ↩️", data="main")
                ]
            ]
            for i in info:
                if i['phone_number'] == phone_number:
                    code = await get_code(i['session'])
                    try:
                        cd = int(code)
                        text = f"الحساب : `+{i['phone_number']}`\nتحقق بخطوتين : `{i['two-step']}`\n✅ الكود : `{code}`\n\nتم ايجاد الكود، سيتم ايقاف الاتصال بالحساب"
                        now = datetime.datetime.now()
                        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
                        bots = await client.get_me()
                        user_info = await client.get_entity(bots.id)
                        keyboards = [
                            [
                                KeyboardButtonUrl("شراء حساب تليجرام", url=f"https://t.me/{user_info.username}"),
                            ]
                        ]
                        if db.exists("trust_channel"):
                            await client.send_message(
                                db.get("trust_channel"),
                                msgs['TRUST_MESSAGE'].format(
                                    name,
                                    f"{phone_number}"[:8],
                                    float(price),
                                    f"{user_id}"[:8],
                                    code,
                                    current_time
                                ),
                                buttons=keyboards,
                                parse_mode="markdown"
                            )
                        
                        # تسجيل الخروج من الجلسة قبل حذفها
                        await logout_from_session(i['session'])
                        
                        # حذف الرقم من القائمة
                        info.remove(i)
                        db.set(f"accounts_{calling_code}", info)
                    except Exception as a:
                        print(f"خطأ في get_code: {a}")
                        text = f"الحساب : `+{i['phone_number']}`\nتحقق بخطوتين : `{i['two-step']}`\n❌ الكود : `{code}`\n\nلم يتم ايجاد الكود."
                    async with bot.conversation(event.chat_id) as x:
                        await x.send_message(text, buttons=keyboard)
            return

        elif data == "add_country":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message("- ارسل الان الدولة مع العلم الخاص بها مثال:\n- مصر 🇪🇬")
                name = await x.get_response()
                await x.send_message(f"- ارسل الان رمز النداء الخاص بدولة {name.text} متبوع بـ + مثال\n: +20")
                calling_code = await x.get_response()
                await x.send_message(f"- ارسل الان سعر الرقم لهذه الدولة بعملة الـ $")  # تغيير من "عملات" إلى "$"
                price = await x.get_response()
                try:
                    am = round(float(price.text), 2)
                except:
                    await x.send_message(f"- رجاء ارسل رقم فقط، اعد تسجيل الدولة")
                    return
                await x.send_message(f"- ارسل الان سعر بيع الارقام لدولة {name.text}")
                sell_price = await x.get_response()
                try:
                    sell_am = round(float(sell_price.text), 2)
                except:
                    await x.send_message(f"- رجاء ارسل رقم فقط، اعد تسجيل الدولة")
                    return
                countries = db.get("countries")
                countries.append({"name": name.text, "calling_code": calling_code.text, "price": am, "sell_price": sell_am})
                db.set("countries", countries)
                await x.send_message(f"- تم حفظ الدولة بنجاح ✅\n- عدد الدول المضافة : {len(countries)}")
                return

        elif data == "del_country":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            countries = db.get("countries")
            buttons = []
            row = []
            for code in countries:
                calling_code = code['calling_code']
                name = code['name']
                price = code['price']
                if len(row) < 2:
                    row.append(Button.inline(text=f"{name} : {float(price):.2f} $", data=f"delete_{calling_code}_{name}_{price}"))  # تغيير من "عملات" إلى "$"
                else:
                    buttons.append(row)
                    row = [Button.inline(text=f"{name} : {float(price):.2f} $", data=f"delete_{calling_code}_{name}_{price}")]  # تغيير من "عملات" إلى "$"
            if row:
                buttons.append(row)

            buttons.append([Button.inline(text="رجوع ↩️", data="main")])
            await event.edit("- اختر الدولة التي تريد حذفها", parse_mode='markdown', buttons=buttons)

        elif data.startswith("delete_"):
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            calling_code = data.split('_')[1]
            name = data.split('_')[2]
            price = data.split('_')[3]
            countries = db.get("countries")
            buttons = [
                [
                    Button.inline("رجوع ↩️", data="del_country")
                ]
            ]
            for data in countries:
                if data["calling_code"] == calling_code:
                    countries.remove(data)
                    await event.edit("- تم حذف الدولة بنجاح ✅", parse_mode='markdown', buttons=buttons)
                    db.set("countries", countries)
                    return
            await event.edit("- فشل حذف الدولة ❌", parse_mode='markdown', buttons=buttons)

        elif data.startswith("countries_"):
            calling_code = data.split('_')[1]
            name = data.split('_')[2]
            price = float(data.split('_')[3])
            user_info = db.get(f"user_{user_id}")
            coins = round(float(user_info.get('coins', 0)), 2) if user_info else 0.0
            
            if coins < price:
                return await event.answer(f"- رصيدك لا يكفي لشراء اي ارقام من هذه الدولة.\n- رصيدك: {coins:.2f} $\n- سعر الرقم: {price:.2f} $", alert=True)
                
            accounts = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
            if accounts == []:
                return await event.answer("- لا توجد أي حسابات في هذه الدولة.", alert=True)
                
            keyboard = [
                [
                    Button.inline("الغاء ❌", data="back"),
                    Button.inline("تأكيد ✅", data=f"buy_{calling_code}_{name}_{price}")
                ],
            ]
            await event.edit(msgs['BUY_MESSAGE'].format(name, price), parse_mode='markdown', buttons=keyboard)
            return

        elif data.startswith("buy_"):
            calling_code = data.split('_')[1]
            name = data.split('_')[2]
            price = float(data.split('_')[3])
            
            # الحصول على معلومات المستخدم والتحقق من الرصيد
            acc = db.get(f"user_{user_id}")
            if not acc:
                return await event.answer("- حدث خطأ في بيانات المستخدم!", alert=True)
                
            current_balance = round(float(acc.get('coins', 0)), 2)
            
            # التحقق من الرصيد بدقة
            if current_balance < price:
                return await event.answer(f"- رصيدك غير كافٍ!\n- رصيدك: {current_balance:.2f} $\n- سعر الرقم: {price:.2f} $", alert=True)
            
            # خصم المبلغ
            acc['coins'] = round(current_balance - price, 2)
            db.set(f"user_{user_id}", acc)
            
            info = db.get(f"accounts_{calling_code}") if db.exists(f"accounts_{calling_code}") else []
            if not info:
                # إعادة الرصيد إذا لم توجد حسابات
                acc['coins'] = current_balance
                db.set(f"user_{user_id}", acc)
                return await event.answer("- عذراً، لم تعد هناك حسابات متاحة في هذه الدولة!", alert=True)
                
            i = random.choice(info)
            text = f"- الحساب : `+{i['phone_number']}`\n- تحقق بخطوتين : `{i['two-step']}`\n- السعر : {price:.2f} $\n- رصيدك الجديد : {acc['coins']:.2f} $\n\n**• قم بتطلب الحصول علي الكود اولا ثم اضغط علي الزر ادناه**"
            keyboard = [
                [
                    Button.inline("الحصول علي الكود", data=f"get:{i['phone_number']}:{calling_code}:{name}:{price}"),
                ]
            ]
            await event.edit(text, buttons=keyboard)

        elif data == "add_admin":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message("- ارسل الان ايدي الادمن الذي تريد رفعه")
                name = await x.get_response()
                try:
                    id = int(name.text)
                except:
                    return await x.send_message("- ارسل الايدي ارقام فقط")
                admins = db.get("admins")
                if id in admins:
                    return await x.send_message("- العضو ادمن بالفعل ❌")
                admins.append(id)
                db.set("admins", admins)
                await x.send_message("- تم اضافة العضو ادمن بنجاح ✅")

        elif data == "del_admin":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message("- ارسل الان ايدي الادمن الذي تريد حذفه")
                name = await x.get_response()
                try:
                    id = int(name.text)
                except:
                    return await x.send_message("- ارسل الايدي ارقام فقط")
                admins = db.get("admins")
                if id not in admins:
                    return await x.send_message("- العضو ليس ادمن بالبوت ❌")
                admins.remove(id)
                db.set("admins", admins)
                await x.send_message("- تم ازالة العضو من الادمن بنجاح ✅")

        elif data == "set_trust_channel":
            if user_id != admin and user_id not in db.get("admins"):
                await event.answer("⛔ هذا القسم للمسؤولين فقط!", alert=True)
                return
                
            async with bot.conversation(event.chat_id) as x:
                await x.send_message(f"- ارسل معرف او رابط قناة اثباتات التسليم.")
                ch = await x.get_response()
                channel = ch.text.replace('https://t.me/', '').replace('@', '').replace(" ", "")
                try:
                    message = "- تم تفعيل قناة اثباتات التسليم بنجاح ✅"
                    await client.send_message(channel, message)
                except:
                    message = "- حدث خطأ ❌، تأكد من رفع البوت ادمن في قناتك مع صلاحية ارسال الرسائل"
                    await x.send_message(message)
                    return
                message = "- تم تفعيل قناة اثباتات التسليم بنجاح ✅"
                await x.send_message(message)
                db.set("trust_channel", channel)

    # Start the bot
    print("Bot is running✅. . . ")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())