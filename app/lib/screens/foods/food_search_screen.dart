// lib/screens/foods/food_search_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants.dart';
import '../../models/models.dart';
import '../../services/recommendation_service.dart';

// ── Provider ──────────────────────────────────────────────
final _queryProvider    = StateProvider<String>((ref) => '');
final _maxCalProvider   = StateProvider<double?>((ref) => null);
final _diabeticProvider = StateProvider<bool>((ref) => false);

final _foodResultsProvider = FutureProvider<List<FoodItem>>((ref) async {
  final q      = ref.watch(_queryProvider);
  final maxCal = ref.watch(_maxCalProvider);
  final diab   = ref.watch(_diabeticProvider);

  return FoodService().searchFoods(
    query:           q.isEmpty ? null : q,
    maxCalories:     maxCal,
    diabeticFriendly: diab ? true : null,
    limit:           30,
  );
});

// ── Screen ────────────────────────────────────────────────
class FoodSearchScreen extends ConsumerStatefulWidget {
  const FoodSearchScreen({super.key});

  @override
  ConsumerState<FoodSearchScreen> createState() => _FoodSearchScreenState();
}

class _FoodSearchScreenState extends ConsumerState<FoodSearchScreen> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final results   = ref.watch(_foodResultsProvider);
    final isDiabetic = ref.watch(_diabeticProvider);
    final maxCal    = ref.watch(_maxCalProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('بحث الأطعمة')),
      body: Column(
        children: [
          // ── Search bar ──────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: TextField(
              controller: _ctrl,
              onChanged: (v) =>
                  ref.read(_queryProvider.notifier).state = v,
              decoration: InputDecoration(
                hintText:    'ابحث عن طعام...',
                prefixIcon:  const Icon(Icons.search),
                suffixIcon: _ctrl.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _ctrl.clear();
                          ref.read(_queryProvider.notifier).state = '';
                        },
                      )
                    : null,
              ),
            ),
          ),

          // ── Filter chips ────────────────────────────────
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(
                horizontal: 16, vertical: 10),
            child: Row(children: [
              // Diabetic friendly toggle
              FilterChip(
                label: const Text('مناسب للسكري'),
                selected:     isDiabetic,
                onSelected:   (v) =>
                    ref.read(_diabeticProvider.notifier).state = v,
                selectedColor: AppColors.secondary.withOpacity(0.2),
                checkmarkColor: AppColors.secondary,
                avatar: const Icon(Icons.monitor_heart_outlined,
                    size: 16),
              ),
              const SizedBox(width: 8),

              // Max calories dropdown
              PopupMenuButton<double?>(
                onSelected: (v) =>
                    ref.read(_maxCalProvider.notifier).state = v,
                itemBuilder: (_) => [
                  const PopupMenuItem(value: null,   child: Text('كل السعرات')),
                  const PopupMenuItem(value: 100.0,  child: Text('أقل من 100 ك')),
                  const PopupMenuItem(value: 200.0,  child: Text('أقل من 200 ك')),
                  const PopupMenuItem(value: 350.0,  child: Text('أقل من 350 ك')),
                  const PopupMenuItem(value: 500.0,  child: Text('أقل من 500 ك')),
                ],
                child: Chip(
                  avatar: const Icon(Icons.local_fire_department_outlined,
                      size: 16, color: AppColors.accent),
                  label: Text(
                    maxCal == null
                        ? 'السعرات'
                        : '< ${maxCal.toStringAsFixed(0)} ك',
                  ),
                  backgroundColor: maxCal != null
                      ? AppColors.accent.withOpacity(0.15)
                      : null,
                ),
              ),

              // Clear filters
              if (isDiabetic || maxCal != null) ...[
                const SizedBox(width: 8),
                ActionChip(
                  label: const Text('مسح'),
                  avatar: const Icon(Icons.filter_alt_off, size: 14),
                  onPressed: () {
                    ref.read(_diabeticProvider.notifier).state = false;
                    ref.read(_maxCalProvider.notifier).state   = null;
                  },
                ),
              ],
            ]),
          ),

          // ── Results ─────────────────────────────────────
          Expanded(
            child: results.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(
                child: Text(e.toString(),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: AppColors.danger)),
              ),
              data: (foods) {
                if (foods.isEmpty) {
                  return const Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.no_food_outlined,
                            size: 56, color: AppColors.textGrey),
                        SizedBox(height: 12),
                        Text('لا توجد نتائج',
                            style: TextStyle(color: AppColors.textGrey)),
                      ],
                    ),
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 80),
                  itemCount:   foods.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: 8),
                  itemBuilder: (_, i) => _FoodTile(food: foods[i]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

// ── Food list tile ────────────────────────────────────────
class _FoodTile extends StatelessWidget {
  final FoodItem food;
  const _FoodTile({required this.food});

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(
              horizontal: 16, vertical: 8),
          leading: CircleAvatar(
            backgroundColor: AppColors.primary.withOpacity(0.1),
            child: Text(
              '${food.calories.toStringAsFixed(0)}',
              style: const TextStyle(
                  fontSize: 11, color: AppColors.primary,
                  fontWeight: FontWeight.bold),
            ),
          ),
          title: Text(food.name,
              style: const TextStyle(
                  fontWeight: FontWeight.w600, fontSize: 14)),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Row(children: [
              _Tag('P ${food.protein.toStringAsFixed(0)}g',
                  AppColors.secondary),
              const SizedBox(width: 6),
              _Tag('C ${food.carbs.toStringAsFixed(0)}g',
                  AppColors.accent),
              const SizedBox(width: 6),
              _Tag('F ${food.fat.toStringAsFixed(0)}g',
                  AppColors.danger),
              if (food.diabeticFriendly) ...[
                const SizedBox(width: 6),
                const Icon(Icons.check_circle_outline,
                    size: 14, color: AppColors.secondary),
              ],
            ]),
          ),
          trailing: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('${food.healthScore.toStringAsFixed(0)}',
                  style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary)),
              const Text('نقاط صحة',
                  style: TextStyle(fontSize: 10,
                      color: AppColors.textGrey)),
            ],
          ),
        ),
      );
}

class _Tag extends StatelessWidget {
  final String text; final Color color;
  const _Tag(this.text, this.color);

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color:        color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(text,
            style: TextStyle(fontSize: 10, color: color,
                fontWeight: FontWeight.w600)),
      );
}
