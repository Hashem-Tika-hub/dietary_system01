// lib/core/theme.dart

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'constants.dart';

class AppTheme {
  static ThemeData get light => ThemeData(
    useMaterial3:     true,
    colorScheme:      ColorScheme.fromSeed(seedColor: AppColors.primary),
    scaffoldBackgroundColor: AppColors.background,

    // Text — Arabic-friendly font
    textTheme: GoogleFonts.cairoTextTheme().copyWith(
      headlineLarge: GoogleFonts.cairo(
          fontSize: 28, fontWeight: FontWeight.bold,
          color: AppColors.textDark),
      headlineMedium: GoogleFonts.cairo(
          fontSize: 22, fontWeight: FontWeight.w700,
          color: AppColors.textDark),
      titleLarge: GoogleFonts.cairo(
          fontSize: 18, fontWeight: FontWeight.w600,
          color: AppColors.textDark),
      bodyLarge: GoogleFonts.cairo(
          fontSize: 16, color: AppColors.textDark),
      bodyMedium: GoogleFonts.cairo(
          fontSize: 14, color: AppColors.textGrey),
    ),

    // AppBar
    appBarTheme: AppBarTheme(
      backgroundColor:  AppColors.surface,
      foregroundColor:  AppColors.textDark,
      elevation:        0,
      centerTitle:      true,
      titleTextStyle:   GoogleFonts.cairo(
          fontSize: 18, fontWeight: FontWeight.w700,
          color: AppColors.textDark),
    ),

    // ElevatedButton
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor:  AppColors.primary,
        foregroundColor:  Colors.white,
        minimumSize:      const Size(double.infinity, 52),
        shape:            RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14)),
        textStyle:        GoogleFonts.cairo(
                            fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),

    // Input fields
    inputDecorationTheme: InputDecorationTheme(
      filled:           true,
      fillColor:        AppColors.surface,
      contentPadding:   const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide:   const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide:   const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide:   const BorderSide(color: AppColors.primary, width: 2),
      ),
      labelStyle:       GoogleFonts.cairo(color: AppColors.textGrey),
    ),

    // Card
    cardTheme: CardThemeData(
      elevation:    0,
      color:        AppColors.surface,
      shape:        RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                      side: const BorderSide(
                              color: AppColors.border, width: 0.5)),
    ),
  );
}