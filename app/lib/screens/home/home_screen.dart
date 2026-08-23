import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_client.dart' show extractError;
import '../../core/constants.dart';
import '../../providers/providers.dart';

/// لوحة التحكم اليومية.
///
/// تعرض هذه الشاشة الأهداف المحسوبة والاستهلاك الفعلي من MealLog كلٌّ منهما
/// بوضوح؛ لذلك لا يُعامل الهدف المخطط على أنه استهلاك تحقق بالفعل.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  Future<void> _refresh(WidgetRef ref) async {
    ref.invalidate(nutritionTargetsProvider);
    ref.invalidate(dailyNutritionProgressProvider);
    ref.invalidate(collaborativeReadinessProvider);
    await Future.wait([
      ref.read(nutritionTargetsProvider.future),
      ref.read(dailyNutritionProgressProvider.future),
      ref.read(collaborativeReadinessProvider.future),
    ]);
  }

  void _openMealRecommendations(BuildContext context, WidgetRef ref, String meal) {
    ref.read(selectedMealProvider.notifier).state = meal;
    context.push('/recommendations');
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final targets = ref.watch(nutritionTargetsProvider);
    final dailyProgress = ref.watch(dailyNutritionProgressProvider);
    final readiness = ref.watch(collaborativeReadinessProvider);
    final user = auth.user!;
    final suggestedMeal = _suggestedMealForNow();

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => _refresh(ref),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
            children: [
              _DashboardHeader(
                firstName: user.name.split(' ').first,
                onProfile: () => context.push('/profile'),
              ),
              const SizedBox(height: 20),

              // 1. الأهداف المخططة مقابل الاستهلاك المأخوذ من سجل الوجبات.
              targets.when(
                loading: () => const _LoadingPanel(height: 220),
                error: (error, _) => _RetryPanel(
                  title: 'تعذّر تحميل أهدافك اليومية',
                  message: extractError(error),
                  onRetry: () => ref.invalidate(nutritionTargetsProvider),
                ),
                data: (target) => dailyProgress.when(
                  loading: () => const _LoadingPanel(height: 220),
                  error: (error, _) => _RetryPanel(
                    title: 'تعذّر تحميل سجل اليوم',
                    message: extractError(error),
                    onRetry: () => ref.invalidate(dailyNutritionProgressProvider),
                  ),
                  data: (progress) => _DailyNutritionCard(
                    targets: target,
                    progress: progress,
                    onRecommend: () => _openMealRecommendations(
                      context,
                      ref,
                      suggestedMeal.key,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // 2. أقصر طريق إلى الاقتراح التالي.
              _NextStepCard(
                meal: suggestedMeal,
                onTap: () => _openMealRecommendations(
                  context,
                  ref,
                  suggestedMeal.key,
                ),
              ),
              const SizedBox(height: 16),

              // 3. شرح صادق لحالة التعلم والتخصيص.
              readiness.when(
                loading: () => const _LoadingPanel(height: 108),
                error: (error, _) => _RetryPanel(
                  title: 'تعذّر قراءة حالة التخصيص',
                  message: extractError(error),
                  onRetry: () => ref.invalidate(collaborativeReadinessProvider),
                  compact: true,
                ),
                data: (state) => _PersonalizationStatusCard(
                  isReady: state.ready,
                  reason: state.reason,
                  interactionCount: state.interactionCount,
                  onExplore: () => _openMealRecommendations(
                    context,
                    ref,
                    suggestedMeal.key,
                  ),
                ),
              ),
              const SizedBox(height: 24),

              _SectionHeader(title: 'ماذا تريد اليوم؟'),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.48,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  _QuickActionCard(
                    title: 'توصية وجبة',
                    subtitle: 'اقتراح مناسب الآن',
                    icon: Icons.restaurant_menu_outlined,
                    color: AppColors.primary,
                    onTap: () => _openMealRecommendations(
                      context,
                      ref,
                      suggestedMeal.key,
                    ),
                  ),
                  _QuickActionCard(
                    title: 'خطة الأسبوع',
                    subtitle: 'أنشئ أو عدّل خطتك',
                    icon: Icons.calendar_month_outlined,
                    color: AppColors.secondary,
                    onTap: () => context.push('/weekly'),
                  ),
                  _QuickActionCard(
                    title: 'بحث الأطعمة',
                    subtitle: 'استكشف الكتالوج',
                    icon: Icons.search_rounded,
                    color: AppColors.accent,
                    onTap: () => context.push('/foods'),
                  ),
                  _QuickActionCard(
                    title: 'ملفي الشخصي',
                    subtitle: 'عدّل القيود والتفضيلات',
                    icon: Icons.person_outline_rounded,
                    color: AppColors.purple,
                    onTap: () => context.push('/profile'),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              _SectionHeader(
                title: 'خطتك الأسبوعية',
                actionLabel: 'فتح الخطة',
                onAction: () => context.push('/weekly'),
              ),
              const SizedBox(height: 10),
              _WeeklyPlanTeaser(onOpen: () => context.push('/weekly')),
              const SizedBox(height: 16),

              const _SafetyNote(),
            ],
          ),
        ),
      ),
    );
  }
}

class _SuggestedMeal {
  final String key;
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;

  const _SuggestedMeal({
    required this.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
  });
}

_SuggestedMeal _suggestedMealForNow() {
  final hour = DateTime.now().hour;
  if (hour < 11) {
    return const _SuggestedMeal(
      key: 'breakfast',
      title: 'ابدأ يومك بالفطور',
      subtitle: 'استكشف اقتراحات الفطور المناسبة لملفك.',
      icon: Icons.wb_sunny_outlined,
      color: AppColors.breakfast,
    );
  }
  if (hour < 16) {
    return const _SuggestedMeal(
      key: 'lunch',
      title: 'وقت اقتراح الغداء',
      subtitle: 'اعرض بدائل الغداء المناسبة لملفك.',
      icon: Icons.lunch_dining_outlined,
      color: AppColors.lunch,
    );
  }
  if (hour < 20) {
    return const _SuggestedMeal(
      key: 'dinner',
      title: 'خطط لعشائك',
      subtitle: 'اطّلع على اقتراحات العشاء المتاحة.',
      icon: Icons.dinner_dining_outlined,
      color: AppColors.dinner,
    );
  }
  return const _SuggestedMeal(
    key: 'snack',
    title: 'اقتراح خفيف لليوم',
    subtitle: 'ابحث عن وجبة خفيفة مناسبة أو راجع خطتك.',
    icon: Icons.apple_outlined,
    color: AppColors.snack,
  );
}

class _DashboardHeader extends StatelessWidget {
  final String firstName;
  final VoidCallback onProfile;

  const _DashboardHeader({required this.firstName, required this.onProfile});

  String _weekdayLabel() {
    const labels = [
      'الاثنين',
      'الثلاثاء',
      'الأربعاء',
      'الخميس',
      'الجمعة',
      'السبت',
      'الأحد',
    ];
    return labels[DateTime.now().weekday - 1];
  }

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'أهلاً، $firstName',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: AppColors.textDark,
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${_weekdayLabel()} · دعنا ننظم خياراتك الغذائية اليوم.',
                  style: const TextStyle(color: AppColors.textGrey, fontSize: 13),
                ),
              ],
            ),
          ),
          IconButton.filledTonal(
            tooltip: 'الملف الشخصي',
            onPressed: onProfile,
            icon: const Icon(Icons.person_outline_rounded),
            color: AppColors.primary,
          ),
        ],
      );
}

class _DailyNutritionCard extends StatelessWidget {
  final dynamic targets;
  final dynamic progress;
  final VoidCallback onRecommend;

  const _DailyNutritionCard({
    required this.targets,
    required this.progress,
    required this.onRecommend,
  });

  @override
  Widget build(BuildContext context) {
    final calories = progress.calories;
    final hasLogs = progress.loggedMeals > 0;
    final remainingLabel = calories.isOverTarget
        ? 'تجاوزت الهدف بـ ${(-calories.remaining).toStringAsFixed(0)} كيلوكالوري'
        : 'متبقٍ ${calories.remaining.toStringAsFixed(0)} كيلوكالوري';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.primary, Color(0xFF1559A8)],
          begin: Alignment.topRight,
          end: Alignment.bottomLeft,
        ),
        borderRadius: BorderRadius.circular(22),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.22),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.track_changes_outlined, color: Colors.white70, size: 18),
              const SizedBox(width: 7),
              const Expanded(
                child: Text('متابعة اليوم',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
              ),
              Text(
                hasLogs ? '${progress.loggedMeals} وجبات مسجلة' : 'لا توجد وجبات مسجلة',
                style: const TextStyle(color: Colors.white70, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '${calories.consumed.toStringAsFixed(0)} / ${calories.target.toStringAsFixed(0)} كيلوكالوري',
            style: const TextStyle(color: Colors.white, fontSize: 27, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 7),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: calories.clampedProgress,
              minHeight: 8,
              color: calories.isOverTarget ? AppColors.accent : Colors.white,
              backgroundColor: Colors.white24,
            ),
          ),
          const SizedBox(height: 7),
          Text(remainingLabel, style: const TextStyle(color: Colors.white70, fontSize: 12)),
          const SizedBox(height: 16),
          Row(
            children: [
              _ConsumedMacroMetric(label: 'بروتين', nutrient: progress.protein),
              _ConsumedMacroMetric(label: 'كارب', nutrient: progress.carbs),
              _ConsumedMacroMetric(label: 'دهون', nutrient: progress.fat),
            ],
          ),
          const SizedBox(height: 15),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: onRecommend,
              icon: const Icon(Icons.auto_awesome_outlined, size: 18),
              label: Text(hasLogs ? 'استكشف توصيات إضافية' : 'استكشف وجبة لتسجيلها'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Colors.white54),
                padding: const EdgeInsets.symmetric(vertical: 11),
              ),
            ),
          ),
          if (!hasLogs) ...[
            const SizedBox(height: 8),
            const Text(
              'سيظهر التقدم بعد إضافة وجبة إلى سجل وجباتك الفعلي.',
              style: TextStyle(color: Colors.white70, fontSize: 11),
            ),
          ],
        ],
      ),
    );
  }
}

class _ConsumedMacroMetric extends StatelessWidget {
  final String label;
  final dynamic nutrient;

  const _ConsumedMacroMetric({required this.label, required this.nutrient});

  @override
  Widget build(BuildContext context) => Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(color: Colors.white70, fontSize: 12)),
            const SizedBox(height: 3),
            Text(
              '${nutrient.consumed.toStringAsFixed(0)} / ${nutrient.target.toStringAsFixed(0)}g',
              style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      );
}

class _NextStepCard extends StatelessWidget {
  final _SuggestedMeal meal;
  final VoidCallback onTap;

  const _NextStepCard({required this.meal, required this.onTap});

  @override
  Widget build(BuildContext context) => Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: meal.color.withOpacity(0.14),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(meal.icon, color: meal.color),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('خطوتك التالية',
                          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                                color: AppColors.textGrey,
                              )),
                      const SizedBox(height: 3),
                      Text(meal.title,
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                      const SizedBox(height: 3),
                      Text(meal.subtitle,
                          style: const TextStyle(fontSize: 12, color: AppColors.textGrey)),
                    ],
                  ),
                ),
                Icon(Icons.arrow_back_ios_new_rounded, size: 17, color: meal.color),
              ],
            ),
          ),
        ),
      );
}

class _PersonalizationStatusCard extends StatelessWidget {
  final bool isReady;
  final String reason;
  final int interactionCount;
  final VoidCallback onExplore;

  const _PersonalizationStatusCard({
    required this.isReady,
    required this.reason,
    required this.interactionCount,
    required this.onExplore,
  });

  @override
  Widget build(BuildContext context) {
    final color = isReady ? AppColors.secondary : AppColors.purple;
    final title = isReady ? 'التخصيص التعاوني متاح' : 'تخصيصك يتطور مع تفاعلك';
    final description = isReady
        ? 'تُستخدم تفاعلات صريحة متاحة لتحسين ترتيب بعض البدائل.'
        : 'سجّل إعجابك أو حفظك أو عدم اهتمامك من الاقتراحات؛ لا يستخدم النظام بيانات مصطنعة.';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        border: Border.all(color: color.withOpacity(0.22)),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(isReady ? Icons.psychology_alt_outlined : Icons.tips_and_updates_outlined,
              color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(color: color, fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Text(description,
                    style: const TextStyle(fontSize: 12, color: AppColors.textGrey)),
                if (reason.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(reason, style: const TextStyle(fontSize: 11, color: AppColors.textGrey)),
                ],
                if (!isReady) ...[
                  const SizedBox(height: 9),
                  TextButton.icon(
                    onPressed: onExplore,
                    icon: const Icon(Icons.favorite_border_rounded, size: 17),
                    label: Text(
                      interactionCount > 0 ? 'أكمل بناء تفضيلاتك' : 'أضف أول تفضيل لك',
                    ),
                    style: TextButton.styleFrom(
                      foregroundColor: color,
                      padding: EdgeInsets.zero,
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  const _SectionHeader({this.actionLabel, this.onAction, required this.title});

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Expanded(
            child: Text(title,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    )),
          ),
          if (actionLabel != null && onAction != null)
            TextButton(onPressed: onAction, child: Text(actionLabel!)),
        ],
      );
}

class _QuickActionCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _QuickActionCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) => Material(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(18),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(18),
          child: Container(
            padding: const EdgeInsets.all(13),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 22),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 3),
                      Text(subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 10, color: AppColors.textGrey)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );
}

class _WeeklyPlanTeaser extends StatelessWidget {
  final VoidCallback onOpen;

  const _WeeklyPlanTeaser({required this.onOpen});

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: AppColors.secondary.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.event_note_outlined, color: AppColors.secondary),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('نظّم أسبوعك بمرونة',
                        style: TextStyle(fontWeight: FontWeight.w700)),
                    SizedBox(height: 4),
                    Text('راجع الخطة، بدّل عنصرًا، أو أنشئ خطة أسبوعية جديدة.',
                        style: TextStyle(fontSize: 12, color: AppColors.textGrey)),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'فتح الخطة الأسبوعية',
                onPressed: onOpen,
                icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 17),
                color: AppColors.secondary,
              ),
            ],
          ),
        ),
      );
}

class _SafetyNote extends StatelessWidget {
  const _SafetyNote();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.textGrey.withOpacity(0.07),
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.info_outline_rounded, color: AppColors.textGrey, size: 19),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                'هذا التطبيق أداة اقتراح غذائي. للحالات الصحية الخاصة أو المعقدة، راجع مختصًا مؤهلًا.',
                style: TextStyle(fontSize: 12, color: AppColors.textGrey, height: 1.45),
              ),
            ),
          ],
        ),
      );
}

class _LoadingPanel extends StatelessWidget {
  final double height;

  const _LoadingPanel({required this.height});

  @override
  Widget build(BuildContext context) => Container(
        height: height,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.border),
        ),
        child: const Center(child: CircularProgressIndicator()),
      );
}

class _RetryPanel extends StatelessWidget {
  final String title;
  final String message;
  final VoidCallback onRetry;
  final bool compact;

  const _RetryPanel({
    required this.title,
    required this.message,
    required this.onRetry,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.danger.withOpacity(0.08),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.danger.withOpacity(0.22)),
        ),
        child: Row(
          children: [
            const Icon(Icons.cloud_off_outlined, color: AppColors.danger),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                  if (!compact) ...[
                    const SizedBox(height: 3),
                    Text(message,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 12, color: AppColors.textGrey)),
                  ],
                ],
              ),
            ),
            TextButton(onPressed: onRetry, child: const Text('إعادة المحاولة')),
          ],
        ),
      );
