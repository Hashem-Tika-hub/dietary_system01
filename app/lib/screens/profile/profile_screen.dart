// lib/screens/profile/profile_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants.dart';
import '../../models/models.dart';
import '../../providers/providers.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user    = ref.watch(authProvider).user!;
    final targets = ref.watch(nutritionTargetsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('ملفي الشخصي'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_outlined, color: AppColors.danger),
            onPressed: () async {
              await ref.read(authProvider.notifier).logout();
              if (context.mounted) context.go('/login');
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Avatar + name
          Center(child: Column(children: [
            CircleAvatar(
              radius: 40,
              backgroundColor: AppColors.primary.withOpacity(0.1),
              child: Text(user.name[0].toUpperCase(),
                  style: const TextStyle(fontSize: 32,
                      color: AppColors.primary, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 12),
            Text(user.name,
                style: Theme.of(context).textTheme.headlineMedium),
            Text(user.email,
                style: const TextStyle(color: AppColors.textGrey)),
          ])),
          const SizedBox(height: 24),

          // Body stats card
          _SectionCard(
            title: 'البيانات الجسدية',
            trailing: TextButton.icon(
              onPressed: () => Navigator.push(context,
                  MaterialPageRoute(builder: (_) => EditProfileScreen(user: user))),
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('تعديل'),
            ),
            children: [
              _InfoRow('العمر',   '${user.age} سنة'),
              _InfoRow('الجنس',   user.gender == 'male' ? 'ذكر' : 'أنثى'),
              _InfoRow('الوزن',   '${user.weight} كجم'),
              _InfoRow('الطول',   '${user.height} سم'),
              _InfoRow('BMI',     user.bmi.toStringAsFixed(1)),
              _InfoRow('الحالة',  user.bmiCategory),
            ],
          ),
          const SizedBox(height: 12),

          // Health card
          _SectionCard(
            title: 'الحالة الصحية',
            trailing: TextButton.icon(
              onPressed: () => Navigator.push(context,
                  MaterialPageRoute(builder: (_) => EditProfileScreen(user: user))),
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('تعديل'),
            ),
            children: [
              _InfoRow('السكري',       user.hasDiabetes    ? '✓ نعم' : '— لا'),
              _InfoRow('ضغط الدم',     user.hasBp          ? '✓ نعم' : '— لا'),
              _InfoRow('الكوليسترول', user.hasCholesterol  ? '✓ نعم' : '— لا'),
            ],
          ),
          const SizedBox(height: 12),

          // Food preferences card
          _SectionCard(
            title: 'تفضيلات الطعام',
            trailing: TextButton.icon(
              onPressed: () => _openEditPreferences(context, ref, user),
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('تعديل'),
            ),
            children: [
              _InfoRow('الطابع',
                  AppConfig.cuisineStyleLabels[user.cuisineStyle] ?? user.cuisineStyle),
              _InfoRow('لا يفضّل',
                  user.dislikes.isEmpty ? '— لا شيء'
                      : user.dislikes.map((k) => AppConfig.foodPrefLabels[k] ?? k).join('، ')),
              _InfoRow('يفضّل أكثر',
                  user.favorites.isEmpty ? '— لا شيء'
                      : user.favorites.map((k) => AppConfig.foodPrefLabels[k] ?? k).join('، ')),
            ],
          ),
          const SizedBox(height: 12),

          // Nutrition targets card
          targets.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error:   (_, __) => const SizedBox(),
            data: (t) => _SectionCard(
              title: 'الاحتياجات اليومية',
              children: [
                _InfoRow('BMR',          '${t.bmr.toStringAsFixed(0)} ك'),
                _InfoRow('TDEE',         '${t.tdee.toStringAsFixed(0)} ك'),
                _InfoRow('الهدف اليومي','${t.dailyCalories.toStringAsFixed(0)} ك'),
                _InfoRow('بروتين',       '${t.proteinG.toStringAsFixed(0)} g'),
                _InfoRow('كربوهيدرات',  '${t.carbsG.toStringAsFixed(0)} g'),
                _InfoRow('دهون',         '${t.fatG.toStringAsFixed(0)} g'),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Goal
          _SectionCard(
            title: 'هدفك',
            trailing: TextButton.icon(
              onPressed: () => Navigator.push(context,
                  MaterialPageRoute(builder: (_) => EditProfileScreen(user: user))),
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('تعديل'),
            ),
            children: [
              _InfoRow('النشاط', AppConfig.activityLabels[user.activityLevel - 1]),
              _InfoRow('الهدف',  AppConfig.goalLabels[user.goal] ?? user.goal),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title; final List<Widget> children; final Widget? trailing;
  const _SectionCard({required this.title, required this.children, this.trailing});

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Text(title, style: Theme.of(context).textTheme.titleLarge),
                const Spacer(),
                if (trailing != null) trailing!,
              ]),
              const Divider(height: 20),
              ...children,
            ],
          ),
        ),
      );
}

class _InfoRow extends StatelessWidget {
  final String label, value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Text(label, style: const TextStyle(color: AppColors.textGrey)),
          const Spacer(),
          Flexible(child: Text(value,
              textAlign: TextAlign.end,
              style: const TextStyle(fontWeight: FontWeight.w600))),
        ]),
      );
}

// ── تعديل المعلومات الشخصية الكاملة ───────────────────────
class EditProfileScreen extends ConsumerStatefulWidget {
  final UserModel user;
  const EditProfileScreen({super.key, required this.user});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late final _nameCtrl   = TextEditingController(text: widget.user.name);
  late final _ageCtrl    = TextEditingController(text: '${widget.user.age}');
  late final _weightCtrl = TextEditingController(text: '${widget.user.weight}');
  late final _heightCtrl = TextEditingController(text: '${widget.user.height}');
  late String _gender         = widget.user.gender;
  late int    _activityLevel  = widget.user.activityLevel;
  late String _goal           = widget.user.goal;
  late bool   _diabetes       = widget.user.hasDiabetes;
  late bool   _bp             = widget.user.hasBp;
  late bool   _cholesterol    = widget.user.hasCholesterol;
  bool _saving = false;

  @override
  void dispose() {
    _nameCtrl.dispose(); _ageCtrl.dispose();
    _weightCtrl.dispose(); _heightCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    final ok = await ref.read(authProvider.notifier).updateProfile({
      'name':           _nameCtrl.text.trim(),
      'age':            int.parse(_ageCtrl.text),
      'gender':         _gender,
      'weight':         double.parse(_weightCtrl.text),
      'height':         double.parse(_heightCtrl.text),
      'activity_level': _activityLevel,
      'goal':           _goal,
      'has_diabetes':   _diabetes,
      'has_bp':         _bp,
      'has_cholesterol':_cholesterol,
    });
    if (mounted) {
      setState(() => _saving = false);
      if (ok) {
        Navigator.pop(context);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('تعذّر حفظ التعديلات، حاول مرة أخرى')));
      }
    }
  }

  String? _numValidator(String? v, {double min = 0, double max = 999}) {
    if (v == null || v.trim().isEmpty) return 'مطلوب';
    final n = double.tryParse(v);
    if (n == null) return 'رقم غير صالح';
    if (n < min || n > max) return 'خارج المدى المسموح';
    return null;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('تعديل المعلومات الشخصية')),
        body: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              TextFormField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'الاسم'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'مطلوب' : null,
              ),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(child: TextFormField(
                  controller: _ageCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'العمر'),
                  validator: (v) => _numValidator(v, min: 10, max: 100),
                )),
                const SizedBox(width: 12),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    value: _gender,
                    decoration: const InputDecoration(labelText: 'الجنس'),
                    items: const [
                      DropdownMenuItem(value: 'male',   child: Text('ذكر')),
                      DropdownMenuItem(value: 'female', child: Text('أنثى')),
                    ],
                    onChanged: (v) => setState(() => _gender = v!),
                  ),
                ),
              ]),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(child: TextFormField(
                  controller: _weightCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'الوزن (كجم)'),
                  validator: (v) => _numValidator(v, min: 30, max: 300),
                )),
                const SizedBox(width: 12),
                Expanded(child: TextFormField(
                  controller: _heightCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'الطول (سم)'),
                  validator: (v) => _numValidator(v, min: 100, max: 250),
                )),
              ]),
              const SizedBox(height: 20),

              Text('مستوى النشاط', style: Theme.of(context).textTheme.titleMedium),
              ...List.generate(AppConfig.activityLabels.length, (i) => RadioListTile<int>(
                value: i + 1, groupValue: _activityLevel,
                onChanged: (v) => setState(() => _activityLevel = v!),
                title: Text(AppConfig.activityLabels[i], style: const TextStyle(fontSize: 14)),
                activeColor: AppColors.primary, dense: true,
                contentPadding: EdgeInsets.zero,
              )),
              const SizedBox(height: 12),

              Text('الهدف', style: Theme.of(context).textTheme.titleMedium),
              ...AppConfig.goalLabels.entries.map((e) => RadioListTile<String>(
                value: e.key, groupValue: _goal,
                onChanged: (v) => setState(() => _goal = v!),
                title: Text(e.value, style: const TextStyle(fontSize: 14)),
                activeColor: AppColors.primary, dense: true,
                contentPadding: EdgeInsets.zero,
              )),
              const SizedBox(height: 12),

              Text('الحالة الصحية', style: Theme.of(context).textTheme.titleMedium),
              SwitchListTile(value: _diabetes, onChanged: (v) => setState(() => _diabetes = v),
                  title: const Text('السكري'), activeColor: AppColors.primary,
                  contentPadding: EdgeInsets.zero),
              SwitchListTile(value: _bp, onChanged: (v) => setState(() => _bp = v),
                  title: const Text('ضغط الدم'), activeColor: AppColors.primary,
                  contentPadding: EdgeInsets.zero),
              SwitchListTile(value: _cholesterol, onChanged: (v) => setState(() => _cholesterol = v),
                  title: const Text('الكوليسترول'), activeColor: AppColors.primary,
                  contentPadding: EdgeInsets.zero),
              const SizedBox(height: 24),

              ElevatedButton(
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(height: 20, width: 20,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Text('حفظ التعديلات'),
              ),
            ],
          ),
        ),
      );
}

// ── تعديل تفضيلات الطعام ──────────────────────────────────
void _openEditPreferences(BuildContext context, WidgetRef ref, UserModel user) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
    builder: (_) => _EditPreferencesSheet(user: user),
  );
}

class _EditPreferencesSheet extends ConsumerStatefulWidget {
  final UserModel user;
  const _EditPreferencesSheet({required this.user});

  @override
  ConsumerState<_EditPreferencesSheet> createState() => _EditPreferencesSheetState();
}

class _EditPreferencesSheetState extends ConsumerState<_EditPreferencesSheet> {
  late Set<String> _dislikes  = {...widget.user.dislikes};
  late Set<String> _favorites = {...widget.user.favorites};
  late String _cuisineStyle   = widget.user.cuisineStyle;
  bool _saving = false;

  Future<void> _save() async {
    setState(() => _saving = true);
    final ok = await ref.read(authProvider.notifier).updateProfile({
      'dislikes':      _dislikes.toList(),
      'favorites':     _favorites.toList(),
      'cuisine_style': _cuisineStyle,
    });
    if (mounted) {
      setState(() => _saving = false);
      if (ok) Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 16, 20,
            MediaQuery.of(context).viewInsets.bottom + 20),
        child: SingleChildScrollView(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Center(child: Container(
              width: 40, height: 4,
              decoration: BoxDecoration(color: AppColors.border,
                  borderRadius: BorderRadius.circular(2)),
            )),
            const SizedBox(height: 16),
            Text('تعديل تفضيلات الطعام',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),

            Text('الطابع المفضّل', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            ...AppConfig.cuisineStyleLabels.entries.map((e) => RadioListTile<String>(
              value: e.key, groupValue: _cuisineStyle,
              onChanged: (v) => setState(() => _cuisineStyle = v!),
              title: Text(e.value, style: const TextStyle(fontSize: 14)),
              activeColor: AppColors.primary, dense: true,
              contentPadding: EdgeInsets.zero,
            )),
            const SizedBox(height: 16),

            Text('لا يفضّلها', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8,
              children: AppConfig.foodPrefLabels.entries.map((e) => FilterChip(
                label: Text(e.value),
                selected: _dislikes.contains(e.key),
                onSelected: (_) => setState(() {
                  if (_dislikes.contains(e.key)) {
                    _dislikes.remove(e.key);
                  } else {
                    _dislikes.add(e.key);
                    _favorites.remove(e.key);
                  }
                }),
                selectedColor: AppColors.danger.withOpacity(0.15),
                checkmarkColor: AppColors.danger,
              )).toList(),
            ),
            const SizedBox(height: 16),

            Text('يفضّلها أكثر', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8,
              children: AppConfig.foodPrefLabels.entries.map((e) => FilterChip(
                label: Text(e.value),
                selected: _favorites.contains(e.key),
                onSelected: (_) => setState(() {
                  if (_favorites.contains(e.key)) {
                    _favorites.remove(e.key);
                  } else {
                    _favorites.add(e.key);
                    _dislikes.remove(e.key);
                  }
                }),
                selectedColor: AppColors.secondary.withOpacity(0.15),
                checkmarkColor: AppColors.secondary,
              )).toList(),
            ),
            const SizedBox(height: 24),

            SizedBox(width: double.infinity, child: ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(height: 20, width: 20,
                      child: CircularProgressIndicator(
                          color: Colors.white, strokeWidth: 2))
                  : const Text('حفظ'),
            )),
          ]),
        ),
      );
}