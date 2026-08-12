// lib/screens/home/home_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../core/constants.dart';
import '../../core/api_client.dart' show extractError;
import '../../providers/providers.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth    = ref.watch(authProvider);
    final targets = ref.watch(nutritionTargetsProvider);
    final user    = auth.user!;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('أهلاً ${user.name.split(' ').first} 👋'),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_outline),
            onPressed: () => context.push('/profile'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(nutritionTargetsProvider.future),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // ── Daily calorie card ───────────────────────
            targets.when(
              loading: () => const _LoadingCard(),
              error:   (e, _) => _ErrorCard(extractError(e)),
              data:    (t) => _CalorieCard(targets: t),
            ),
            const SizedBox(height: 16),

            // ── Macro distribution ───────────────────────
            targets.when(
              loading: () => const _LoadingCard(height: 180),
              error:   (_, __) => const SizedBox(),
              data:    (t) => _MacroCard(targets: t),
            ),
            const SizedBox(height: 16),

            // ── Quick actions ────────────────────────────
            Text('ماذا تريد اليوم؟',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: _ActionCard(
                label: 'توصية وجبة',
                icon:  Icons.restaurant_outlined,
                color: AppColors.primary,
                onTap: () => context.push('/recommendations'),
              )),
              const SizedBox(width: 12),
              Expanded(child: _ActionCard(
                label: 'خطة الأسبوع',
                icon:  Icons.calendar_month_outlined,
                color: AppColors.secondary,
                onTap: () => context.push('/weekly'),
              )),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: _ActionCard(
                label: 'بحث الأطعمة',
                icon:  Icons.search_rounded,
                color: AppColors.accent,
                onTap: () => context.push('/foods'),
              )),
              const SizedBox(width: 12),
              Expanded(child: _ActionCard(
                label: 'ملفي الشخصي',
                icon:  Icons.person_outline,
                color: AppColors.purple,
                onTap: () => context.push('/profile'),
              )),
            ]),
          ],
        ),
      ),
    );
  }
}

// ── Calorie summary card ──────────────────────────────────
class _CalorieCard extends StatelessWidget {
  final dynamic targets;
  const _CalorieCard({required this.targets});

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(children: [
            Text('هدفك اليومي',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              '${targets.dailyCalories.toStringAsFixed(0)} كيلوكالوري',
              style: const TextStyle(
                  fontSize: 32, fontWeight: FontWeight.bold,
                  color: AppColors.primary),
            ),
            const SizedBox(height: 16),
            Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
              _MacroChip('بروتين', targets.proteinG, AppColors.secondary),
              _MacroChip('كارب', targets.carbsG, AppColors.accent),
              _MacroChip('دهون', targets.fatG, AppColors.danger),
            ]),
          ]),
        ),
      );
}

class _MacroChip extends StatelessWidget {
  final String label;
  final double value;
  final Color  color;
  const _MacroChip(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) => Column(children: [
        Text(label, style: const TextStyle(
            fontSize: 12, color: AppColors.textGrey)),
        const SizedBox(height: 4),
        Text('${value.toStringAsFixed(0)}g',
            style: TextStyle(
                fontSize: 18, fontWeight: FontWeight.bold, color: color)),
      ]);
}

// ── Macro pie chart ───────────────────────────────────────
class _MacroCard extends StatelessWidget {
  final dynamic targets;
  const _MacroCard({required this.targets});

  @override
  Widget build(BuildContext context) {
    final protein = targets.proteinG * 4;
    final carbs   = targets.carbsG   * 4;
    final fat     = targets.fatG     * 9;
    final total   = protein + carbs + fat;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          Text('توزيع المغذيات',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          SizedBox(
            height: 150,
            child: PieChart(PieChartData(
              sectionsSpace: 2,
              centerSpaceRadius: 40,
              sections: [
                PieChartSectionData(
                    value: protein, color: AppColors.secondary,
                    title: '${(protein/total*100).toStringAsFixed(0)}%',
                    radius: 50, titleStyle: const TextStyle(
                        color: Colors.white, fontSize: 12)),
                PieChartSectionData(
                    value: carbs, color: AppColors.accent,
                    title: '${(carbs/total*100).toStringAsFixed(0)}%',
                    radius: 50, titleStyle: const TextStyle(
                        color: Colors.white, fontSize: 12)),
                PieChartSectionData(
                    value: fat, color: AppColors.danger,
                    title: '${(fat/total*100).toStringAsFixed(0)}%',
                    radius: 50, titleStyle: const TextStyle(
                        color: Colors.white, fontSize: 12)),
              ],
            )),
          ),
          const SizedBox(height: 12),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            _Legend('بروتين', AppColors.secondary),
            const SizedBox(width: 16),
            _Legend('كارب', AppColors.accent),
            const SizedBox(width: 16),
            _Legend('دهون', AppColors.danger),
          ]),
        ]),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  final String label; final Color color;
  const _Legend(this.label, this.color);
  @override
  Widget build(BuildContext context) => Row(children: [
        Container(width: 12, height: 12,
            decoration: BoxDecoration(
                color: color, borderRadius: BorderRadius.circular(3))),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 12)),
      ]);
}

// ── Quick action card ─────────────────────────────────────
class _ActionCard extends StatelessWidget {
  final String label; final IconData icon;
  final Color color; final VoidCallback onTap;
  const _ActionCard({required this.label, required this.icon,
      required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color:        color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: color.withOpacity(0.3)),
          ),
          child: Column(children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 8),
            Text(label, textAlign: TextAlign.center,
                style: TextStyle(color: color, fontWeight: FontWeight.w600)),
          ]),
        ),
      );
}

class _LoadingCard extends StatelessWidget {
  final double height;
  const _LoadingCard({this.height = 130});
  @override
  Widget build(BuildContext context) => Container(
        height: height,
        decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16)),
        child: const Center(child: CircularProgressIndicator()),
      );
}

class _ErrorCard extends StatelessWidget {
  final String message;
  const _ErrorCard(this.message);
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
            color: AppColors.danger.withOpacity(0.1),
            borderRadius: BorderRadius.circular(16)),
        child: Text(message,
            style: const TextStyle(color: AppColors.danger),
            textAlign: TextAlign.center),
      );
}