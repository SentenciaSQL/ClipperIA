import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Professional dark theme for the desktop editing shell.
class AppTheme {
  const AppTheme._();

  static const Color background = Color(0xFF0E1116);
  static const Color surface = Color(0xFF161B22);
  static const Color surfaceAlt = Color(0xFF1C2330);
  static const Color border = Color(0xFF2A3341);
  static const Color accent = Color(0xFF3DDC97);
  static const Color accentMuted = Color(0xFF2A9D6E);
  static const Color danger = Color(0xFFE35D6A);
  static const Color warning = Color(0xFFE0A458);
  static const Color textPrimary = Color(0xFFE8EEF6);
  static const Color textSecondary = Color(0xFF9AA7B8);

  static ThemeData get dark {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme.dark(
        surface: surface,
        primary: accent,
        secondary: accentMuted,
        error: danger,
        onPrimary: Color(0xFF04140E),
        onSurface: textPrimary,
      ),
    );

    return base.copyWith(
      textTheme: GoogleFonts.ibmPlexSansTextTheme(base.textTheme).apply(
        bodyColor: textPrimary,
        displayColor: textPrimary,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: surface,
        foregroundColor: textPrimary,
        elevation: 0,
        titleTextStyle: GoogleFonts.ibmPlexSans(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
      ),
      navigationRailTheme: const NavigationRailThemeData(
        backgroundColor: surface,
        selectedIconTheme: IconThemeData(color: accent),
        unselectedIconTheme: IconThemeData(color: textSecondary),
        indicatorColor: Color(0x223DDC97),
      ),
      cardTheme: const CardTheme(
        color: surfaceAlt,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          side: BorderSide(color: border),
        ),
      ),
      dividerColor: border,
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: accent),
        ),
      ),
    );
  }
}
