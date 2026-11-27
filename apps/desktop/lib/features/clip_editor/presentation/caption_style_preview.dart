import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Renders a caption style sample using the same ASS-oriented fields as export.
class CaptionStylePreview extends StatelessWidget {
  const CaptionStylePreview({
    super.key,
    required this.style,
    this.sample = 'ESTO ES INCREÍBLE, NO TE LO PUEDES PERDER',
    this.selected = false,
    this.label,
    this.onTap,
    this.height = 110,
  });

  final Map<String, dynamic> style;
  final String sample;
  final bool selected;
  final String? label;
  final VoidCallback? onTap;
  final double height;

  static Color assToColor(String? ass, {Color fallback = Colors.white}) {
    if (ass == null || ass.isEmpty) return fallback;
    var value = ass.trim().toUpperCase();
    if (value.startsWith('&H')) value = value.substring(2);
    if (value.length < 6) return fallback;
    // ASS: AABBGGRR
    final padded = value.padLeft(8, '0');
    final aa = int.tryParse(padded.substring(0, 2), radix: 16) ?? 0;
    final bb = int.tryParse(padded.substring(2, 4), radix: 16) ?? 0;
    final gg = int.tryParse(padded.substring(4, 6), radix: 16) ?? 0;
    final rr = int.tryParse(padded.substring(6, 8), radix: 16) ?? 255;
    // ASS alpha: 00 opaque, FF transparent
    final opacity = ((255 - aa).clamp(0, 255)) / 255.0;
    return Color.fromRGBO(rr, gg, bb, opacity);
  }

  @override
  Widget build(BuildContext context) {
    final fontName = style['font_name']?.toString() ?? 'Arial';
    final fontSize = ((style['font_size'] as num?)?.toDouble() ?? 48) / 3.2;
    final bold = style['bold'] == true || style['bold'] == 1;
    final primary = assToColor(style['primary_colour']?.toString());
    final outlineColor = assToColor(
      style['outline_colour']?.toString(),
      fallback: Colors.black,
    );
    final back = assToColor(
      style['back_colour']?.toString(),
      fallback: Colors.black54,
    );
    final outline = (style['outline'] as num?)?.toDouble() ?? 0;
    final shadow = (style['shadow'] as num?)?.toDouble() ?? 0;
    final bgOpacity = (style['background_opacity'] as num?)?.toDouble();
    final borderStyle = (style['border_style'] as num?)?.toInt() ?? 1;
    final alignment = (style['alignment'] as num?)?.toInt() ?? 2;
    final textAlign = switch (alignment) {
      1 || 4 || 7 => TextAlign.left,
      3 || 6 || 9 => TextAlign.right,
      _ => TextAlign.center,
    };

    Color? boxColor;
    if (borderStyle == 3 || (bgOpacity != null && bgOpacity > 0.05)) {
      boxColor = back.withOpacity(
        bgOpacity ?? (back.opacity == 0 ? 0.45 : back.opacity),
      );
    }

    final shadows = <Shadow>[];
    if (outline > 0) {
      final o = outline.clamp(1.0, 4.0).toDouble();
      for (final dx in <double>[-o, 0.0, o]) {
        for (final dy in <double>[-o, 0.0, o]) {
          if (dx == 0 && dy == 0) continue;
          shadows.add(Shadow(offset: Offset(dx, dy), color: outlineColor));
        }
      }
    }
    if (shadow > 0) {
      shadows.add(
        Shadow(
          offset: Offset(shadow, shadow),
          blurRadius: shadow,
          color: Colors.black.withOpacity(0.75),
        ),
      );
    }

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          height: height,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: selected ? AppTheme.accent : AppTheme.border,
              width: selected ? 2 : 1,
            ),
          ),
          clipBehavior: Clip.antiAlias,
          child: Stack(
            fit: StackFit.expand,
            children: [
              // Simulated video backdrop
              const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      Color(0xFF1A2330),
                      Color(0xFF0B3D2E),
                      Color(0xFF243044),
                    ],
                  ),
                ),
              ),
              Positioned(
                left: 12,
                right: 12,
                bottom: 14,
                child: Align(
                  alignment: alignment >= 7
                      ? Alignment.topCenter
                      : alignment >= 4
                          ? Alignment.center
                          : Alignment.bottomCenter,
                  child: Container(
                    padding: boxColor != null
                        ? const EdgeInsets.symmetric(horizontal: 10, vertical: 4)
                        : EdgeInsets.zero,
                    color: boxColor,
                    child: Text(
                      sample,
                      textAlign: textAlign,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontFamily: fontName,
                        fontSize: fontSize.clamp(11, 28),
                        fontWeight: bold ? FontWeight.w800 : FontWeight.w500,
                        color: primary,
                        height: 1.15,
                        letterSpacing: (style['spacing'] as num?)?.toDouble(),
                        shadows: shadows,
                      ),
                    ),
                  ),
                ),
              ),
              if (label != null)
                Positioned(
                  left: 8,
                  top: 8,
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    color: Colors.black54,
                    child: Text(
                      label!,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textPrimary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
