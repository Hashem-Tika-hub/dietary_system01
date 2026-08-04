# ============================================================
#  api/routes/auth.py — مسارات المصادقة
#  POST /auth/register — تسجيل مستخدم جديد
#  POST /auth/login    — تسجيل الدخول
#  GET  /auth/me       — بيانات المستخدم الحالي
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.database    import get_db
from api.db_models   import User
from api.schemas     import UserRegister, UserLogin, Token, UserResponse
from api.auth        import hash_password, verify_password, create_token
from api.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["المصادقة"])


@router.post("/register", response_model=Token, status_code=201,
             summary="تسجيل مستخدم جديد")
def register(data: UserRegister, db: Session = Depends(get_db)):
    """
    تسجيل مستخدم جديد في النظام

    - يتحقق من عدم تكرار البريد الإلكتروني
    - يشفّر كلمة المرور
    - يُرجع JWT Token فور التسجيل
    """
    # تحقق من عدم تكرار البريد
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="البريد الإلكتروني مسجّل مسبقاً"
        )

    # إنشاء المستخدم
    user = User(
        email           = data.email,
        hashed_password = hash_password(data.password),
        name            = data.name,
        age             = data.age,
        gender          = data.gender,
        weight          = data.weight,
        height          = data.height,
        activity_level  = data.activity_level,
        goal            = data.goal,
        has_diabetes    = data.has_diabetes,
        has_bp          = data.has_bp,
        has_cholesterol = data.has_cholesterol,
        allergies       = data.allergies,
        dislikes        = data.dislikes,
        favorites       = data.favorites,
        cuisine_style   = data.cuisine_style,
        allow_treats    = data.allow_treats,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token({"sub": str(user.id)})
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=Token, summary="تسجيل الدخول")
def login(data: UserLogin, db: Session = Depends(get_db)):
    """
    تسجيل الدخول بالبريد وكلمة المرور
    يُرجع JWT Token صالح لمدة 30 يوم
    """
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بريد إلكتروني أو كلمة مرور غير صحيحة"
        )

    token = create_token({"sub": str(user.id)})
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse, summary="بيانات المستخدم الحالي")
def get_me(current_user: User = Depends(get_current_user)):
    """استرجاع بيانات المستخدم المسجَّل حالياً"""
    return current_user