# ============================================================
#  api/db_models.py — جداول قاعدة البيانات
# ============================================================

from datetime import datetime
from sqlalchemy import (Column, Integer, Float, String,
                        Boolean, DateTime, Text, ForeignKey, JSON)
from sqlalchemy.orm import relationship
from api.database import Base


class User(Base):
    """جدول المستخدمين"""
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name            = Column(String(100), default="مستخدم")
    created_at      = Column(DateTime, default=datetime.utcnow)

    # بيانات الجسم
    age             = Column(Integer,  nullable=False)
    gender          = Column(String(10), default="male")
    weight          = Column(Float,    nullable=False)   # كجم
    height          = Column(Float,    nullable=False)   # سم
    activity_level  = Column(Integer,  default=2)        # 1-5

    # الهدف والصحة
    goal            = Column(String(20), default="maintain")
    has_diabetes    = Column(Boolean, default=False)
    has_bp          = Column(Boolean, default=False)
    has_cholesterol = Column(Boolean, default=False)
    allergies       = Column(JSON,    default=list)      # ["gluten","lactose",...]

    # تفضيلات الطعام التفصيلية (أُضيفت لدعم أسئلة تفصيلية أكثر بالتسجيل)
    dislikes        = Column(JSON,    default=list)      # ["بحريات",...] لا تُستبعد كليًا
    favorites       = Column(JSON,    default=list)      # ["دواجن",...] تُرجَّح بالترتيب فقط
    cuisine_style   = Column(String(20), default="مزيج") # تقليدي / عالمي / مزيج
    allow_treats    = Column(Boolean, default=False)      # إظهار حلويات كخيار مناسبات

    # علاقات
    meal_logs   = relationship("MealLog",   back_populates="user",
                               cascade="all, delete")
    weekly_plans = relationship("WeeklyPlan", back_populates="user",
                                cascade="all, delete")


class MealLog(Base):
    """سجل الوجبات المتناولة"""
    __tablename__ = "meal_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    date        = Column(DateTime, default=datetime.utcnow)
    meal_type   = Column(String(20))          # breakfast/lunch/dinner/snack
    food_name   = Column(String(255))
    fdc_id      = Column(String(50))
    portion_g   = Column(Float, default=100)
    calories    = Column(Float, default=0)
    protein     = Column(Float, default=0)
    carbs       = Column(Float, default=0)
    fat         = Column(Float, default=0)
    notes       = Column(Text,  default="")

    user = relationship("User", back_populates="meal_logs")


class WeeklyPlan(Base):
    """الخطط الأسبوعية المُولَّدة"""
    __tablename__ = "weekly_plans"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    plan_data  = Column(JSON, nullable=False)   # الخطة الكاملة كـ JSON

    user = relationship("User", back_populates="weekly_plans")