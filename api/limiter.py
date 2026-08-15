# ============================================================
#  api/limiter.py — تحديد معدّل الطلبات (rate limiting)
#  ملف منفصل بمفرده عشان main.py وroutes/auth.py يقدروا يستوردوا
#  limiter بدون circular import بينهم
# ============================================================
from slowapi import Limiter
from slowapi.util import get_remote_address

# المفتاح الافتراضي هو IP المرسل. لو التطبيق راح يشتغل خلف reverse
# proxy (nginx/Heroku) لازم تتأكد إن X-Forwarded-For يوصل صحيح وإلا
# كل الطلبات راح تُحسب على نفس IP (IP الـ proxy).
limiter = Limiter(key_func=get_remote_address)
