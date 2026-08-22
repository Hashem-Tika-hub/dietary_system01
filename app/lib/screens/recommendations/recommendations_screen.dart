import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart' show extractError;
import '../../core/constants.dart';
import '../../models/models.dart';
import '../../providers/providers.dart';

class RecommendationsScreen extends ConsumerWidget {
  const RecommendationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('توصيات الوجبات'),
          bottom: TabBar(
            onTap: (index) => ref.read(selectedMealProvider.notifier).state =
                AppConfig.meals[index],
            isScrollable: false,
            labelColor: AppColors.primary,
            unselectedLabelColor: AppColors.textGrey,
            indicatorColor: AppColors.primary,
            tabs: AppConfig.meals
                .map((meal) => Tab(text: AppConfig.mealsAr[meal]))
                .toList(),
          ),
        ),
        body: TabBarView(
          children: AppConfig.meals.map((meal) => _MealTab(meal: meal)).toList(),
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
    final recommendations = ref.watch(mealRecommendationsProvider(meal));

    return recommendations.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: AppColors.danger, size: 48),
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Text(extractError(error), textAlign: TextAlign.center),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => ref.invalidate(mealRecommendationsProvider(meal)),
              child: const Text('إعادة المحاولة'),
            ),
          ],
        ),
      ),
      data: (data) => _MealRecommendationView(data: data),
    );
  }
}

class _MealRecommendationView extends ConsumerWidget {
  final MealRecommendation data;
  const _MealRecommendationView({required this.data});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final readiness = ref.watch(collaborativeReadinessProvider);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.primary, Color(0xFF5B9FE8)],
            ),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            children: [
              const Icon(Icons.flag_outlined, color: Colors.white, size: 28),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'هدف الوجبة',
                    style: TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                  Text(
                    '${data.targetCalories.toStringAsFixed(0)} كيلوكالوري',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        _RankingBasisCard(data: data),
        const SizedBox(height: 12),
        _CollaborativeReadinessCard(readiness: readiness),
        const SizedBox(height: 16),
        Text(
          '${data.recommendations.length} اقتراحات لك',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 12),
        ...data.recommendations.asMap().entries.map(
              (entry) => _FoodCard(food: entry.value, rank: entry.key + 1),
            ),
      ],
    );
  }
}

class _RankingBasisCard extends StatelessWidget {
  final MealRecommendation data;
  const _RankingBasisCard({required this.data});

  @override
  Widget build(BuildContext context) {
    final usesCollaborative = data.rankingBasis != 'content_based';
    final label = usesCollaborative
        ? 'ترتيب هجين: ملفك وتفاعلات صريحة مؤهلة'
        : 'ترتيب حسب ملفك الغذائي وتفضيلاتك';

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.secondary.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.secondary.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Icon(
            usesCollaborative ? Icons.auto_graph : Icons.tune,
            color: AppColors.secondary,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 3),
                Text(
                  usesCollaborative
                      ? 'المحتوى ${(data.contentWeight * 100).round()}% · التفاعل ${(data.collaborativeWeight * 100).round()}%'
                      : 'يبدأ النظام بهذا المسار عند عدم كفاية التفاعلات.',
                  style: const TextStyle(fontSize: 12, color: AppColors.textGrey),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CollaborativeReadinessCard extends StatelessWidget {
  final AsyncValue<CollaborativeReadiness> readiness;
  const _CollaborativeReadinessCard({required this.readiness});

  @override
  Widget build(BuildContext context) {
    return readiness.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (state) {
        final color = state.ready ? AppColors.secondary : AppColors.primary;
        final title = state.ready
            ? 'التخصيص من التفاعل جاهز'
            : 'زد دقة التخصيص بتفاعلك';
        final detail = state.ready
            ? 'أصبحت إشارات التفاعل الصريحة مؤهلة لدعم ترتيب التوصيات.'
            : 'قيّم الأطعمة التي تظهر لك. لديك ${state.targetUserInteractions} تفاعلًا صريحًا حتى الآن.';

        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: color.withOpacity(0.07),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color.withOpacity(0.18)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(state.ready ? Icons.verified_outlined : Icons.touch_app_outlined,
                  color: color),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: TextStyle(fontWeight: FontWeight.w600, color: color)),
                    const SizedBox(height: 3),
                    Text(detail, style: const TextStyle(fontSize: 12, color: AppColors.textGrey)),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _FoodCard extends ConsumerWidget {
  final FoodRecommendation food;
  final int rank;
  const _FoodCard({required this.food, required this.rank});

  Future<void> _submitFeedback(
    BuildContext context,
    WidgetRef ref,
    String eventType,
    String message,
  ) async {
    final success = await ref.read(foodFeedbackProvider.notifier).submit(
          fdcId: food.fdcId,
          eventType: eventType,
        );
    if (!context.mounted) return;

    if (success) {
      ref.invalidate(collaborativeReadinessProvider);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تعذّر حفظ تفاعلك، حاول مرة أخرى')),
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedbackLoading = ref.watch(foodFeedbackProvider).isLoading;
    final reasons = food.recommendationReasons.isNotEmpty
        ? food.recommendationReasons
        : (food.recommendationReason.isEmpty ? <String>[] : [food.recommendationReason]);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: rank == 1
                        ? AppColors.accent
                        : AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    food.slot.isNotEmpty ? food.slot : '$rank',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: rank == 1 ? Colors.white : AppColors.primary,
                      fontSize: 12,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    food.name,
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.secondary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${(food.hybridScore * 100).toStringAsFixed(0)}%',
                    style: const TextStyle(
                      color: AppColors.secondary,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.05),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'الحصة الموصى بها',
                    style: TextStyle(color: AppColors.textGrey, fontSize: 13),
                  ),
                  Text(
                    '${food.portionG.toStringAsFixed(0)} جرام',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _MacroItem('سعرات', food.calories, 'ك', AppColors.accent),
                _MacroItem('بروتين', food.protein, 'g', AppColors.secondary),
                _MacroItem('كارب', food.carbs, 'g', AppColors.primary),
                _MacroItem('دهون', food.fat, 'g', AppColors.danger),
              ],
            ),
            if (reasons.isNotEmpty || food.diversityApplied) ...[
              const Divider(height: 24),
              if (reasons.isNotEmpty)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.lightbulb_outline, size: 18, color: AppColors.accent),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        reasons.join(' · '),
                        style: const TextStyle(fontSize: 12, color: AppColors.textGrey),
                      ),
                    ),
                  ],
                ),
              if (food.diversityApplied) ...[
                const SizedBox(height: 8),
                Chip(
                  avatar: const Icon(Icons.diversity_2, size: 16, color: AppColors.secondary),
                  label: const Text('اختيار متنوع في الخطة', style: TextStyle(fontSize: 12)),
                  backgroundColor: AppColors.secondary.withOpacity(0.08),
                  side: BorderSide(color: AppColors.secondary.withOpacity(0.2)),
                ),
              ],
            ],
            const Divider(height: 24),
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'هل يناسبك هذا الاقتراح؟',
                    style: TextStyle(fontSize: 12, color: AppColors.textGrey),
                  ),
                ),
                _FeedbackButton(
                  icon: Icons.thumb_up_outlined,
                  tooltip: 'أعجبني',
                  color: AppColors.secondary,
                  enabled: !feedbackLoading,
                  onPressed: () => _submitFeedback(context, ref, 'like', 'تم تسجيل إعجابك'),
                ),
                _FeedbackButton(
                  icon: Icons.bookmark_add_outlined,
                  tooltip: 'حفظ',
                  color: AppColors.primary,
                  enabled: !feedbackLoading,
                  onPressed: () => _submitFeedback(context, ref, 'save', 'تم حفظ الطعام كتفضيل'),
                ),
                _FeedbackButton(
                  icon: Icons.thumb_down_outlined,
                  tooltip: 'لا يعجبني',
                  color: AppColors.danger,
                  enabled: !feedbackLoading,
                  onPressed: () => _submitFeedback(context, ref, 'dislike', 'سنتجنب ترشيحه قدر الإمكان'),
                ),
                _FeedbackButton(
                  icon: Icons.visibility_off_outlined,
                  tooltip: 'غير مهتم',
                  color: AppColors.textGrey,
                  enabled: !feedbackLoading,
                  onPressed: () => _submitFeedback(context, ref, 'not_interested', 'تم تسجيل أنك غير مهتم'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _FeedbackButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final Color color;
  final bool enabled;
  final VoidCallback onPressed;

  const _FeedbackButton({
    required this.icon,
    required this.tooltip,
    required this.color,
    required this.enabled,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) => IconButton(
        tooltip: tooltip,
        icon: Icon(icon, color: color, size: 20),
        onPressed: enabled ? onPressed : null,
      );
}

class _MacroItem extends StatelessWidget {
  final String label;
  final double value;
  final String unit;
  final Color color;
  const _MacroItem(this.label, this.value, this.unit, this.color);

  @override
  Widget build(BuildContext context) => Column(
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textGrey)),
          const SizedBox(height: 2),
          Text(
            '${value.toStringAsFixed(1)}$unit',
            style: TextStyle(fontWeight: FontWeight.bold, color: color, fontSize: 13),
          ),
        ],
      );
}
