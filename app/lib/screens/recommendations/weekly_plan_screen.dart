// lib/screens/recommendations/weekly_plan_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants.dart';
import '../../core/api_client.dart' show extractError;
import '../../providers/providers.dart';
import '../../models/models.dart';
import '../../services/recommendation_service.dart';

class WeeklyPlanScreen extends ConsumerStatefulWidget {
  const WeeklyPlanScreen({super.key});

  @override
  ConsumerState<WeeklyPlanScreen> createState() => _WeeklyPlanScreenState();
}

class _WeeklyPlanScreenState extends ConsumerState<WeeklyPlanScreen> {
  @override
  void initState() {
    super.initState();
    // يحمّل الخطة المحفوظة الحالية (يولّد مرة واحدة فقط أول مرة) —
    // لا يولّد خطة عشوائية جديدة في كل مرة تُفتح الشاشة
    Future.microtask(() => ref.read(weeklyPlanProvider.notifier).loadCurrent());
  }

  Future<void> _confirmRegenerate() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('توليد خطة جديدة؟'),
        content: const Text(
            'هذا سيستبدل خطتك الأسبوعية الحالية كاملة بخطة جديدة. '
            'أي تعديلات سويتها بالخطة الحالية (استبدال وجبات) ستُفقَد.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
              child: const Text('إلغاء')),
          FilledButton(onPressed: () => Navigator.pop(context, true),
              child: const Text('نعم، ولّد جديدة')),
        ],
      ),
    );
    if (ok == true) {
      ref.read(weeklyPlanProvider.notifier).regenerate();
    }
  }

  @override
  Widget build(BuildContext context) {
    final planAsync = ref.watch(weeklyPlanProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('الخطة الأسبوعية'),
        actions: [
          IconButton(
            tooltip: 'خطة جديدة',
            icon: const Icon(Icons.refresh),
            onPressed: _confirmRegenerate,
          ),
        ],
      ),
      body: planAsync.when(
        loading: () => const Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('جارٍ تحميل خطتك...'),
          ]),
        ),
        error: (e, _) => Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.error_outline,
                color: AppColors.danger, size: 48),
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(extractError(e), textAlign: TextAlign.center),
            ),
            ElevatedButton(
              onPressed: () =>
                  ref.read(weeklyPlanProvider.notifier).loadCurrent(),
              child: const Text('إعادة المحاولة'),
            ),
          ]),
        ),
        data: (data) {
          final plan   = data['plan'] as Map<String, dynamic>? ?? {};
          final totals = data['totals'] as Map? ?? const {};
          final planId = data['id'] as int?;
          if (plan.isEmpty || planId == null) {
            return Center(child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.calendar_today_outlined,
                    size: 64, color: AppColors.textGrey),
                const SizedBox(height: 16),
                const Text('لا توجد خطة بعد'),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  icon: const Icon(Icons.auto_awesome),
                  label: const Text('توليد الخطة الأسبوعية'),
                  onPressed: () =>
                      ref.read(weeklyPlanProvider.notifier).regenerate(),
                ),
              ],
            ));
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: plan.entries.map((e) => _DayCard(
                  day: e.key,
                  meals: e.value as Map,
                  dayTotals: totals[e.key] as Map? ?? const {},
                  planId: planId,
                )).toList(),
          );
        },
      ),
    );
  }
}

class _DayCard extends StatefulWidget {
  final String day;
  final Map meals;
  final Map dayTotals;
  final int planId;
  const _DayCard({
    required this.day,
    required this.meals,
    required this.dayTotals,
    required this.planId,
  });

  @override
  State<_DayCard> createState() => _DayCardState();
}

class _DayCardState extends State<_DayCard> {
  @override
  Widget build(BuildContext context) {
    final calories = (widget.dayTotals['calories'] as num?)?.toDouble() ?? 0;
    final planned = (widget.dayTotals['planned_calories'] as num?)?.toDouble() ?? 0;
    final delta = (widget.dayTotals['calorie_delta'] as num?)?.toDouble() ?? 0;
    final deltaLabel = delta > 0 ? '+${delta.toStringAsFixed(0)}' : delta.toStringAsFixed(0);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        initiallyExpanded: widget.day == 'الأحد',
        title: Row(children: [
          const Icon(Icons.today_outlined, color: AppColors.primary, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(widget.day, style: const TextStyle(fontWeight: FontWeight.bold)),
          ),
          if (widget.dayTotals.isNotEmpty)
            Text(
              '${calories.toStringAsFixed(0)} / ${planned.toStringAsFixed(0)} ك · $deltaLabel',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: delta.abs() <= 25 ? AppColors.secondary : AppColors.textGrey,
              ),
            ),
        ]),
        children: (widget.meals.entries.toList()).map((e) {
          final mealKey  = e.key as String;
          final foods    = e.value as List? ?? [];
          return _MealSection(
              day: widget.day, mealKey: mealKey, foods: foods,
              planId: widget.planId);
        }).toList(),
      ),
    );
  }
}

class _MealSection extends ConsumerWidget {
  final String day, mealKey;
  final List   foods;
  final int    planId;
  const _MealSection({
    required this.day, required this.mealKey, required this.foods,
    required this.planId,
  });

  Color get _color => const {
    'breakfast': AppColors.breakfast,
    'lunch':     AppColors.lunch,
    'dinner':    AppColors.dinner,
    'snack':     AppColors.snack,
  }[mealKey] ?? AppColors.primary;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Container(width: 10, height: 10,
                  decoration: BoxDecoration(
                      color: _color, shape: BoxShape.circle)),
              const SizedBox(width: 6),
              Text(AppConfig.mealsAr[mealKey] ?? mealKey,
                  style: TextStyle(color: _color,
                      fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 6),
            ...foods.map((f) {
              final name = f['name'] ?? '';
              final cal  = (f['calories'] ?? 0).toStringAsFixed(0);
              final g    = (f['portion_g'] ?? 0).toStringAsFixed(0);
              final reason = f['recommendation_reason']?.toString() ?? '';
              final diversityApplied = f['diversity_applied'] == true;
              return InkWell(
                onTap: () => _openSwapSheet(context, ref, f),
                borderRadius: BorderRadius.circular(8),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        const Icon(Icons.restaurant, size: 14,
                            color: AppColors.textGrey),
                        const SizedBox(width: 6),
                        Expanded(child: Text(name,
                            style: const TextStyle(fontSize: 13))),
                        Text('${g}g · ${cal}ك',
                            style: TextStyle(fontSize: 11,
                                color: _color, fontWeight: FontWeight.w500)),
                        const SizedBox(width: 4),
                        const Icon(Icons.swap_horiz, size: 16,
                            color: AppColors.textGrey),
                      ]),
                      if (reason.isNotEmpty || diversityApplied)
                        Padding(
                          padding: const EdgeInsets.only(top: 4, right: 20),
                          child: Row(children: [
                            Icon(diversityApplied ? Icons.diversity_2 : Icons.lightbulb_outline,
                                size: 13, color: AppColors.secondary),
                            const SizedBox(width: 4),
                            Expanded(child: Text(
                              reason.isNotEmpty
                                  ? reason
                                  : 'اختيار متنوع لتقليل التكرار',
                              style: const TextStyle(fontSize: 11, color: AppColors.textGrey),
                            )),
                          ]),
                        ),
                    ],
                  ),
                ),
              );
              // slot يُستخدم داخل _openSwapSheet أدناه
            }),
            const Divider(height: 16),
          ],
        ),
      );

  void _openSwapSheet(BuildContext context, WidgetRef ref, Map food) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => _SwapSheet(
        planId: planId, day: day, meal: mealKey,
        slot: food['slot'] ?? '', currentName: food['name'] ?? '',
      ),
    );
  }
}

class _SwapSheet extends ConsumerStatefulWidget {
  final int planId; final String day, meal, slot, currentName;
  const _SwapSheet({
    required this.planId, required this.day, required this.meal,
    required this.slot, required this.currentName,
  });

  @override
  ConsumerState<_SwapSheet> createState() => _SwapSheetState();
}

class _SwapSheetState extends ConsumerState<_SwapSheet> {
  List<FoodRecommendation>? _alternatives;
  String? _error;
  bool _swapping = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final alts = await RecommendationService().getSwapAlternatives(
        planId: widget.planId, day: widget.day, meal: widget.meal,
        slot: widget.slot,
      );
      if (mounted) setState(() => _alternatives = alts);
    } catch (e) {
      if (mounted) setState(() => _error = 'تعذّر تحميل البدائل');
    }
  }

  Future<void> _pick(FoodRecommendation alt) async {
    setState(() => _swapping = true);
    final updated = await ref.read(weeklyPlanProvider.notifier).swapItem(
      day: widget.day, meal: widget.meal, slot: widget.slot,
      newFdcId: alt.fdcId,
    );
    if (!mounted) return;

    Navigator.pop(context);
    if (updated == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تعذّر تنفيذ الاستبدال، حاول مرة أخرى')),
      );
      return;
    }

    final summary = updated['change_summary'] as Map?;
    final delta = (summary?['meal_calories_delta'] as num?)?.toDouble();
    if (delta != null) {
      final signed = delta > 0 ? '+${delta.toStringAsFixed(0)}' : delta.toStringAsFixed(0);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('تم الاستبدال. فرق سعرات الوجبة: $signed كيلوكالوري')),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 16, 20,
            MediaQuery.of(context).viewInsets.bottom + 20),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Center(child: Container(
            width: 40, height: 4,
            decoration: BoxDecoration(color: AppColors.border,
                borderRadius: BorderRadius.circular(2)),
          )),
          const SizedBox(height: 16),
          Text('استبدال "${widget.currentName}"',
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center),
          const SizedBox(height: 4),
          const Text('اختر بديلاً من نفس المجموعة الغذائية',
              style: TextStyle(color: AppColors.textGrey, fontSize: 12)),
          const SizedBox(height: 16),
          if (_error != null)
            Padding(padding: const EdgeInsets.all(24),
                child: Text(_error!, style: const TextStyle(color: AppColors.danger)))
          else if (_alternatives == null)
            const Padding(padding: EdgeInsets.all(32),
                child: CircularProgressIndicator())
          else if (_alternatives!.isEmpty)
            const Padding(padding: EdgeInsets.all(24),
                child: Text('لا توجد بدائل مناسبة متاحة حاليًا'))
          else
            ConstrainedBox(
              constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.5),
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: _alternatives!.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (_, i) {
                  final a = _alternatives![i];
                  return ListTile(
                    enabled: !_swapping,
                    leading: const Icon(Icons.restaurant_menu, color: AppColors.primary),
                    title: Text(a.name),
                    subtitle: Text('${a.portionG.toStringAsFixed(0)}g · '
                        '${a.calories.toStringAsFixed(0)} سعرة · '
                        'بروتين ${a.protein.toStringAsFixed(0)}g'),
                    trailing: _swapping
                        ? const SizedBox(width: 20, height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.chevron_left),
                    onTap: _swapping ? null : () => _pick(a),
                  );
                },
              ),
            ),
        ]),
      );
}