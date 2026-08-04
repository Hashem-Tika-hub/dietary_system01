// lib/screens/auth/register_screen.dart
// ── 3-step registration: Personal → Health → Goals ───────

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants.dart';
import '../../providers/providers.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _pageCtrl = PageController();
  int _step = 0;

  // ── Form data ─────────────────────────────────────────
  final _name  = TextEditingController();
  final _email = TextEditingController();
  final _pass  = TextEditingController();
  int     _age    = 25;
  String  _gender = 'male';
  double  _weight = 75;
  double  _height = 170;
  int     _activity = 2;
  String  _goal   = 'maintain';
  bool    _diabetes    = false;
  bool    _bp          = false;
  bool    _cholesterol = false;
  final Set<String> _dislikes  = {};
  final Set<String> _favorites = {};
  String  _cuisineStyle = 'مزيج';

  void _next() {
    if (_step < 3) {
      setState(() => _step++);
      _pageCtrl.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      _submit();
    }
  }

  void _back() {
    if (_step > 0) {
      setState(() => _step--);
      _pageCtrl.previousPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      context.go('/login');
    }
  }

  Future<void> _submit() async {
    final ok = await ref.read(authProvider.notifier).register({
      'email':           _email.text.trim(),
      'password':        _pass.text,
      'name':            _name.text.trim(),
      'age':             _age,
      'gender':          _gender,
      'weight':          _weight,
      'height':          _height,
      'activity_level':  _activity,
      'goal':            _goal,
      'has_diabetes':    _diabetes,
      'has_bp':          _bp,
      'has_cholesterol': _cholesterol,
      'allergies':       [],
      'dislikes':        _dislikes.toList(),
      'favorites':       _favorites.toList(),
      'cuisine_style':   _cuisineStyle,
    });
    if (ok && mounted) context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final steps = ['معلوماتك الشخصية', 'جسمك ونشاطك', 'صحتك وهدفك', 'تفضيلات طعامك'];

    return Scaffold(
      appBar: AppBar(
        leading: BackButton(onPressed: _back),
        title: Text(steps[_step]),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: LinearProgressIndicator(
            value: (_step + 1) / 4,
            color: AppColors.primary,
            backgroundColor: AppColors.border,
          ),
        ),
      ),
      body: PageView(
        controller: _pageCtrl,
        physics: const NeverScrollableScrollPhysics(),
        children: [
          _Step1(name: _name, email: _email, pass: _pass),
          _Step2(
            gender:   _gender, age: _age,
            weight:   _weight, height: _height, activity: _activity,
            onGender:   (v) => setState(() => _gender = v),
            onAge:      (v) => setState(() => _age = v),
            onWeight:   (v) => setState(() => _weight = v),
            onHeight:   (v) => setState(() => _height = v),
            onActivity: (v) => setState(() => _activity = v),
          ),
          _Step3(
            goal:        _goal,
            diabetes:    _diabetes, bp: _bp, cholesterol: _cholesterol,
            onGoal:      (v) => setState(() => _goal = v),
            onDiabetes:  (v) => setState(() => _diabetes = v),
            onBp:        (v) => setState(() => _bp = v),
            onCholesterol: (v) => setState(() => _cholesterol = v),
          ),
          _Step4(
            dislikes: _dislikes, favorites: _favorites,
            cuisineStyle: _cuisineStyle,
            onDislikes: (k) => setState(() {
              if (_dislikes.contains(k)) {
                _dislikes.remove(k);
              } else {
                _dislikes.add(k);
                _favorites.remove(k); // لا يكون مفضّلاً وغير مرغوب بنفس الوقت
              }
            }),
            onFavorites: (k) => setState(() {
              if (_favorites.contains(k)) {
                _favorites.remove(k);
              } else {
                _favorites.add(k);
                _dislikes.remove(k);
              }
            }),
            onCuisineStyle: (v) => setState(() => _cuisineStyle = v),
          ),
        ],
      ),
      bottomNavigationBar: Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (auth.error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(auth.error!,
                    style: const TextStyle(color: AppColors.danger),
                    textAlign: TextAlign.center),
              ),
            ElevatedButton(
              onPressed: auth.isLoading ? null : _next,
              child: auth.isLoading
                  ? const SizedBox(height: 22, width: 22,
                      child: CircularProgressIndicator(
                          color: Colors.white, strokeWidth: 2))
                  : Text(_step < 3 ? 'التالي' : 'إنشاء الحساب'),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Step 1: Name, Email, Password ────────────────────────
class _Step1 extends StatelessWidget {
  final TextEditingController name, email, pass;
  const _Step1({required this.name, required this.email, required this.pass});

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(children: [
          TextFormField(controller: name,
              decoration: const InputDecoration(labelText: 'الاسم الكامل',
                  prefixIcon: Icon(Icons.person_outline))),
          const SizedBox(height: 14),
          TextFormField(controller: email,
              keyboardType: TextInputType.emailAddress,
              textDirection: TextDirection.ltr,
              decoration: const InputDecoration(labelText: 'البريد الإلكتروني',
                  prefixIcon: Icon(Icons.email_outlined))),
          const SizedBox(height: 14),
          TextFormField(controller: pass, obscureText: true,
              decoration: const InputDecoration(labelText: 'كلمة المرور (6+ أحرف)',
                  prefixIcon: Icon(Icons.lock_outline))),
        ]),
      );
}

// ── Step 2: Age, Weight, Height, Activity ────────────────
class _Step2 extends StatelessWidget {
  final String gender; final int age, activity;
  final double weight, height;
  final ValueChanged<String> onGender;
  final ValueChanged<int>    onAge, onActivity;
  final ValueChanged<double> onWeight, onHeight;

  const _Step2({required this.gender, required this.age,
    required this.weight, required this.height, required this.activity,
    required this.onGender, required this.onAge, required this.onWeight,
    required this.onHeight, required this.onActivity});

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Gender
          Text('الجنس', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: _GenderBtn('ذكر', 'male', gender, onGender)),
            const SizedBox(width: 12),
            Expanded(child: _GenderBtn('أنثى', 'female', gender, onGender)),
          ]),
          const SizedBox(height: 20),

          // Age
          _SliderTile('العمر', '$age سنة', age.toDouble(), 15, 80,
              (v) => onAge(v.round())),
          _SliderTile('الوزن', '${weight.toStringAsFixed(1)} كجم', weight, 40, 150,
              onWeight),
          _SliderTile('الطول', '${height.toStringAsFixed(0)} سم', height, 140, 210,
              onHeight),

          // Activity
          Text('مستوى النشاط', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          ...List.generate(5, (i) => RadioListTile<int>(
            value: i + 1, groupValue: activity,
            onChanged: (v) => onActivity(v!),
            title: Text(AppConfig.activityLabels[i],
                style: const TextStyle(fontSize: 13)),
            activeColor: AppColors.primary,
            dense: true,
          )),
        ]),
      );
}

class _GenderBtn extends StatelessWidget {
  final String label, value, selected;
  final ValueChanged<String> onTap;
  const _GenderBtn(this.label, this.value, this.selected, this.onTap);

  @override
  Widget build(BuildContext context) {
    final active = value == selected;
    return GestureDetector(
      onTap: () => onTap(value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: active ? AppColors.primary : AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: active ? AppColors.primary : AppColors.border),
        ),
        alignment: Alignment.center,
        child: Text(label,
            style: TextStyle(
                color:      active ? Colors.white : AppColors.textDark,
                fontWeight: FontWeight.w600)),
      ),
    );
  }
}

class _SliderTile extends StatelessWidget {
  final String label, display;
  final double value, min, max;
  final ValueChanged<double> onChanged;
  const _SliderTile(this.label, this.display, this.value,
      this.min, this.max, this.onChanged);

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(label, style: Theme.of(context).textTheme.titleLarge),
            const Spacer(),
            Text(display, style: const TextStyle(
                color: AppColors.primary, fontWeight: FontWeight.bold)),
          ]),
          Slider(value: value, min: min, max: max, onChanged: onChanged,
              activeColor: AppColors.primary),
          const SizedBox(height: 8),
        ],
      );
}

// ── Step 3: Goal + Health conditions ─────────────────────
class _Step3 extends StatelessWidget {
  final String goal;
  final bool diabetes, bp, cholesterol;
  final ValueChanged<String> onGoal;
  final ValueChanged<bool> onDiabetes, onBp, onCholesterol;

  const _Step3({required this.goal, required this.diabetes,
    required this.bp, required this.cholesterol,
    required this.onGoal, required this.onDiabetes,
    required this.onBp, required this.onCholesterol});

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('هدفك الغذائي', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ...AppConfig.goalLabels.entries.map((e) => RadioListTile<String>(
            value: e.key, groupValue: goal,
            onChanged: (v) => onGoal(v!),
            title: Text(e.value),
            activeColor: AppColors.primary,
          )),
          const Divider(height: 32),
          Text('الحالة الصحية', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          SwitchListTile(value: diabetes, onChanged: onDiabetes,
              title: const Text('السكري'),
              secondary: const Icon(Icons.monitor_heart_outlined,
                  color: AppColors.danger),
              activeColor: AppColors.primary),
          SwitchListTile(value: bp, onChanged: onBp,
              title: const Text('ضغط الدم'),
              secondary: const Icon(Icons.bloodtype_outlined,
                  color: AppColors.danger),
              activeColor: AppColors.primary),
          SwitchListTile(value: cholesterol, onChanged: onCholesterol,
              title: const Text('الكوليسترول'),
              secondary: const Icon(Icons.favorite_outline,
                  color: AppColors.danger),
              activeColor: AppColors.primary),
        ]),
      );
}

// ── Step 4: تفضيلات الطعام (جديد) ────────────────────────
class _Step4 extends StatelessWidget {
  final Set<String> dislikes, favorites;
  final String cuisineStyle;
  final ValueChanged<String> onDislikes, onFavorites, onCuisineStyle;

  const _Step4({
    required this.dislikes, required this.favorites,
    required this.cuisineStyle,
    required this.onDislikes, required this.onFavorites,
    required this.onCuisineStyle,
  });

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('الطابع المفضّل للوجبات',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          ...AppConfig.cuisineStyleLabels.entries.map((e) => RadioListTile<String>(
            value: e.key, groupValue: cuisineStyle,
            onChanged: (v) => onCuisineStyle(v!),
            title: Text(e.value),
            activeColor: AppColors.primary,
            dense: true,
          )),
          const Divider(height: 32),

          Text('أطعمة لا تفضّلها', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 4),
          const Text('تُستبعد كليًا من خططك — يمكنك تركها فارغة',
              style: TextStyle(color: AppColors.textGrey, fontSize: 12)),
          const SizedBox(height: 10),
          Wrap(spacing: 8, runSpacing: 8,
            children: AppConfig.foodPrefLabels.entries.map((e) => FilterChip(
              label: Text(e.value),
              selected: dislikes.contains(e.key),
              onSelected: (_) => onDislikes(e.key),
              selectedColor: AppColors.danger.withOpacity(0.15),
              checkmarkColor: AppColors.danger,
              labelStyle: TextStyle(
                color: dislikes.contains(e.key) ? AppColors.danger : AppColors.textDark,
                fontWeight: dislikes.contains(e.key) ? FontWeight.w600 : FontWeight.normal,
              ),
            )).toList(),
          ),
          const SizedBox(height: 24),

          Text('أطعمة تفضّلها أكثر', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 4),
          const Text('تظهر بشكل أكبر بخططك — يمكنك تركها فارغة',
              style: TextStyle(color: AppColors.textGrey, fontSize: 12)),
          const SizedBox(height: 10),
          Wrap(spacing: 8, runSpacing: 8,
            children: AppConfig.foodPrefLabels.entries.map((e) => FilterChip(
              label: Text(e.value),
              selected: favorites.contains(e.key),
              onSelected: (_) => onFavorites(e.key),
              selectedColor: AppColors.secondary.withOpacity(0.15),
              checkmarkColor: AppColors.secondary,
              labelStyle: TextStyle(
                color: favorites.contains(e.key) ? AppColors.secondary : AppColors.textDark,
                fontWeight: favorites.contains(e.key) ? FontWeight.w600 : FontWeight.normal,
              ),
            )).toList(),
          ),
        ]),
      );
}