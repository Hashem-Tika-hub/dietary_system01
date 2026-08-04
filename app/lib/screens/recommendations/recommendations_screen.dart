// lib/screens/recommendations/recommendations_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants.dart';
import '../../providers/providers.dart';
import '../../models/models.dart';

class RecommendationsScreen extends ConsumerWidget {
  const RecommendationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedMeal = ref.watch(selectedMealProvider);

    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('توصيات الوجبات'),
          bottom: TabBar(
            onTap: (i) => ref.read(selectedMealProvider.notifier)
                .state = AppConfig.meals[i],
            isScrollable: false,
            labelColor: AppColors.primary,
            unselectedLabelColor: AppColors.textGrey,
            indicatorColor: AppColors.primary,
            tabs: AppConfig.meals.map((m) =>
                Tab(text: AppConfig.mealsAr[m])).toList(),
          ),
        ),
        body: TabBarView(
          children: AppConfig.meals.map((meal) =>
              _MealTab(meal: meal)).toList(),
        ),
      ),
    );
  }
}

class _MealTab extends ConsumerWidget {
  final String meal;
  const _MealTab({required this.meal});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recs = ref.watch(mealRecommendationsProvider(meal));

    return recs.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error:   (e, _) => Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.error_outline, color: AppColors.danger, size: 48),
            const SizedBox(height: 12),
            Text(e.toString(), textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => ref.invalidate(mealRecommendationsProvider(meal)),
              child: const Text('إعادة المحاولة'),
            ),
          ])),
      data: (data) => _MealRecommendationView(data: data),
    );
  }
}

class _MealRecommendationView extends StatelessWidget {
  final MealRecommendation data;
  const _MealRecommendationView({required this.data});

  @override
  Widget build(BuildContext context) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Target calories card
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppColors.primary, Color(0xFF5B9FE8)]),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(children: [
              const Icon(Icons.flag_outlined, color: Colors.white, size: 28),
              const SizedBox(width: 12),
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('هدف الوجبة',
                    style: TextStyle(color: Colors.white70, fontSize: 13)),
                Text('${data.targetCalories.toStringAsFixed(0)} كيلوكالوري',
                    style: const TextStyle(
                        color: Colors.white, fontSize: 20,
                        fontWeight: FontWeight.bold)),
              ]),
            ]),
          ),
          const SizedBox(height: 16),

          Text('${data.recommendations.length} اقتراحات لك',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),

          ...data.recommendations.asMap().entries.map((e) =>
              _FoodCard(food: e.value, rank: e.key + 1)),
        ],
      );
}

class _FoodCard extends StatelessWidget {
  final FoodRecommendation food;
  final int rank;
  const _FoodCard({required this.food, required this.rank});

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                // Slot badge (بروتين/نشويات/خضار...) — يعكس بنية الطبق
                // الجديدة بدل رقم ترتيب لم يعد ذا معنى بعد اعتماد القالب
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: rank == 1
                        ? AppColors.accent
                        : AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(food.slot.isNotEmpty ? food.slot : '$rank',
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: rank == 1
                              ? Colors.white
                              : AppColors.primary,
                          fontSize: 12)),
                ),
                const SizedBox(width: 12),
                Expanded(child: Text(food.name,
                    style: const TextStyle(
                        fontWeight: FontWeight.w600, fontSize: 15))),
                // Score chip
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.secondary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${(food.hybridScore * 100).toStringAsFixed(0)}%',
                    style: const TextStyle(
                        color: AppColors.secondary,
                        fontWeight: FontWeight.bold,
                        fontSize: 12),
                  ),
                ),
              ]),
              const SizedBox(height: 12),

              // Portion info
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.05),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                  Text('الحصة الموصى بها',
                      style: TextStyle(color: AppColors.textGrey,
                          fontSize: 13)),
                  Text('${food.portionG.toStringAsFixed(0)} جرام',
                      style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: AppColors.primary)),
                ]),
              ),
              const SizedBox(height: 10),

              // Macros row
              Row(mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                _MacroItem('سعرات', food.calories, 'ك', AppColors.accent),
                _MacroItem('بروتين', food.protein, 'g', AppColors.secondary),
                _MacroItem('كارب', food.carbs, 'g', AppColors.primary),
                _MacroItem('دهون', food.fat, 'g', AppColors.danger),
              ]),
            ],
          ),
        ),
      );
}

class _MacroItem extends StatelessWidget {
  final String label; final double value;
  final String unit; final Color color;
  const _MacroItem(this.label, this.value, this.unit, this.color);

  @override
  Widget build(BuildContext context) => Column(children: [
        Text(label,
            style: const TextStyle(fontSize: 11, color: AppColors.textGrey)),
        const SizedBox(height: 2),
        Text('${value.toStringAsFixed(1)}$unit',
            style: TextStyle(fontWeight: FontWeight.bold,
                color: color, fontSize: 13)),
      ]);
}