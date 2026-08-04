# Flutter App — Setup & Run Guide

## Project Structure

```
app/
├── lib/
│   ├── main.dart                          ← Entry point + routing
│   ├── core/
│   │   ├── constants.dart                 ← Colors, API URL, config
│   │   ├── theme.dart                     ← App theme (Cairo font)
│   │   └── api_client.dart                ← Dio HTTP + JWT injection
│   ├── models/
│   │   └── models.dart                    ← User, Food, Recommendation
│   ├── services/
│   │   ├── auth_service.dart              ← register, login, profile
│   │   └── recommendation_service.dart    ← meals, weekly plan, foods
│   ├── providers/
│   │   └── providers.dart                 ← Riverpod state management
│   └── screens/
│       ├── splash_screen.dart             ← auth check + redirect
│       ├── auth/
│       │   ├── login_screen.dart
│       │   └── register_screen.dart       ← 3-step registration
│       ├── home/
│       │   └── home_screen.dart           ← dashboard + pie chart
│       ├── recommendations/
│       │   ├── recommendations_screen.dart← tabbed meal suggestions
│       │   └── weekly_plan_screen.dart    ← 7-day plan
│       ├── profile/
│       │   └── profile_screen.dart        ← user stats + logout
│       └── foods/
│           └── food_search_screen.dart    ← search + filter foods
└── pubspec.yaml
```

---

## Step 1 — Install Flutter

Download Flutter SDK: https://docs.flutter.dev/get-started/install

```powershell
# Verify installation
flutter doctor
```

All items should be green (or with minor warnings about optional tools).

---

## Step 2 — Create the Flutter project

```powershell
# In the dietary-system/app/ folder
cd dietary-system\app

# If this is a fresh folder, initialize a Flutter project:
flutter create . --org com.dietary --platforms android,ios

# This creates: android/, ios/, test/ folders
# Our lib/ files will override the default ones
```

---

## Step 3 — Add internet permission (Android)

Open `android/app/src/main/AndroidManifest.xml` and add:

```xml
<!-- Inside <manifest> tag, before <application> -->
<uses-permission android:name="android.permission.INTERNET"/>
```

Also add `android:usesCleartextTraffic="true"` to the `<application>` tag
(required for HTTP to localhost during development):

```xml
<application
    android:label="dietary_app"
    android:usesCleartextTraffic="true"
    ...>
```

> See `AndroidManifest_template.xml` in this folder for the complete file.

---

## Step 4 — Set your API URL

Open `lib/core/constants.dart` and update `baseUrl`:

```dart
// Android emulator → use this
static const String baseUrl = 'http://10.0.2.2:8000';

// Real Android device on same WiFi → use your PC's IP
static const String baseUrl = 'http://192.168.1.X:8000';

// iOS simulator → use this
static const String baseUrl = 'http://localhost:8000';
```

**Find your PC's IP:**
```powershell
ipconfig    # Windows → look for IPv4 Address
```

---

## Step 5 — Install packages

```powershell
flutter pub get
```

Expected output: `Got dependencies!`

---

## Step 6 — Run the app

Make sure the FastAPI server is running first:
```powershell
# In a separate terminal, from dietary-system/
python run_api.py
```

Then run the Flutter app:
```powershell
# List available devices
flutter devices

# Run on Android emulator
flutter run -d emulator-5554

# Run on connected phone
flutter run -d <device-id>

# Run as web (for quick testing)
flutter run -d chrome
```

---

## App Flow

```
Splash Screen
    ↓ (has saved token?)
    ├── YES → Home Screen
    └── NO  → Login Screen
                  ↓
              Register Screen (3 steps)
                  ↓
              Home Screen
                  ├── Recommendations → Meal tabs (Breakfast/Lunch/Dinner/Snack)
                  ├── Weekly Plan     → 7-day expandable plan
                  ├── Food Search     → Search + filter food database
                  └── Profile         → User stats + logout
```

---

## Screens Preview

| Screen | Description |
|--------|-------------|
| **Splash** | Animated logo, auto-redirects |
| **Login** | Email + password, JWT stored securely |
| **Register** | 3-step: info → body → health/goal |
| **Home** | Daily calorie goal + macro pie chart |
| **Recommendations** | 4 tabs (meals), each with 5 AI suggestions |
| **Weekly Plan** | Expandable 7-day plan, regenerate anytime |
| **Food Search** | Search by name, filter by calories/health |
| **Profile** | BMI, BMR, TDEE, health flags, logout |

---

## Common Errors & Fixes

| Error | Fix |
|-------|-----|
| `SocketException: Connection refused` | Is `python run_api.py` running? |
| `XMLHttpRequest error` | Wrong IP in `constants.dart` |
| `flutter: pub get failed` | Run `flutter pub get` again |
| `Gradle build failed` | Run `flutter clean && flutter pub get` |
| `No devices found` | Enable USB debugging on phone or start emulator |
| `DioException 401` | Token expired — logout and login again |
| Arabic text not showing | Confirm `Directionality(rtl)` is in `main.dart` |

---

## Packages Used

| Package | Version | Purpose |
|---------|---------|---------|
| `dio` | ^5.4.0 | HTTP requests to FastAPI |
| `flutter_riverpod` | ^2.4.9 | State management |
| `go_router` | ^13.0.0 | Navigation & routing |
| `flutter_secure_storage` | ^9.0.0 | Secure JWT token storage |
| `fl_chart` | ^0.67.0 | Pie chart on home screen |
| `google_fonts` | ^6.1.0 | Cairo Arabic font |
