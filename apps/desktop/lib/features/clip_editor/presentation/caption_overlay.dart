import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import 'caption_style_preview.dart';

/// Draggable caption layer drawn ABOVE the video Opacity layer.
/// Uses PlayRes 1080×1920 normalized coordinates to match ASS export.
class CaptionOverlayLayer extends StatelessWidget {
  const CaptionOverlayLayer({
    super.key,
    required this.text,
    required this.style,
    required this.selected,
    required this.onSelect,
    required this.onStyleChanged,
    this.playResX = 1080,
    this.playResY = 1920,
  });

  final String text;
  final Map<String, dynamic> style;
  final bool selected;
  final VoidCallback onSelect;
  final ValueChanged<Map<String, dynamic>> onStyleChanged;
  final double playResX;
  final double playResY;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        final h = constraints.maxHeight;
        if (w <= 0 || h <= 0) return const SizedBox.shrink();

        final alignment = (style['alignment'] as num?)?.toInt() ?? 2;
        final marginV = (style['margin_v'] as num?)?.toDouble() ?? 80;
        final marginL = (style['margin_l'] as num?)?.toDouble() ?? 40;
        final marginR = (style['margin_r'] as num?)?.toDouble() ?? 40;
        final maxWidthPx = (style['max_width'] as num?)?.toDouble() ?? playResX;
        final boxWidth = (maxWidthPx / playResX * w).clamp(80.0, w);

        double left;
        double top;
        final posX = style['pos_x'];
        final posY = style['pos_y'];
        if (posX is num && posY is num) {
          left = (posX.toDouble() / playResX * w) - boxWidth / 2;
          top = posY.toDouble() / playResY * h;
        } else {
          // ASS alignment → approximate placement
          final xFrac = switch (alignment) {
            1 || 4 || 7 => marginL / playResX,
            3 || 6 || 9 => 1.0 - (marginR / playResX) - (boxWidth / w),
            _ => (w - boxWidth) / 2 / w,
          };
          left = xFrac * w;
          final fromBottom = alignment <= 3;
          final fromTop = alignment >= 7;
          if (fromTop) {
            top = marginV / playResY * h;
          } else if (fromBottom) {
            top = h - (marginV / playResY * h) - 48;
          } else {
            top = h / 2 - 24;
          }
        }

        left = left.clamp(0.0, w - boxWidth);
        top = top.clamp(0.0, h - 40);

        final fontSize =
            ((style['font_size'] as num?)?.toDouble() ?? 48) / playResY * h;
        final bold = style['bold'] == true ||
            style['bold'] == 1 ||
            ((style['font_weight'] as num?)?.toInt() ?? 400) >= 600;
        final italic = style['italic'] == true || style['italic'] == 1;
        final primary = CaptionStylePreview.assToColor(
          style['primary_colour']?.toString(),
        ).withOpacity(
          ((style['text_opacity'] as num?)?.toDouble() ?? 1.0).clamp(0.0, 1.0),
        );
        final outlineColor = CaptionStylePreview.assToColor(
          style['outline_colour']?.toString(),
          fallback: Colors.black,
        );
        final back = CaptionStylePreview.assToColor(
          style['back_colour']?.toString(),
          fallback: Colors.black54,
        );
        final bgOpacity =
            ((style['background_opacity'] as num?)?.toDouble() ?? 0).clamp(0.0, 1.0);
        final outline = (style['outline'] as num?)?.toDouble() ?? 0;
        final shadow = (style['shadow'] as num?)?.toDouble() ?? 0;
        final borderStyle = (style['border_style'] as num?)?.toInt() ?? 1;
        final radius = (style['corner_radius'] as num?)?.toDouble() ?? 0;
        final pad = (style['padding'] as num?)?.toDouble() ?? 8;

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

        Color? boxColor;
        if (borderStyle == 3 || bgOpacity > 0.05) {
          boxColor = back.withOpacity(bgOpacity == 0 ? 0.45 : bgOpacity);
        }

        return Stack(
          children: [
            Positioned(
              left: left,
              top: top,
              width: boxWidth,
              child: GestureDetector(
                onTap: onSelect,
                onPanUpdate: (details) {
                  final nx = ((left + boxWidth / 2 + details.delta.dx) / w)
                      .clamp(0.0, 1.0);
                  final ny = ((top + details.delta.dy) / h).clamp(0.0, 1.0);
                  onStyleChanged({
                    ...style,
                    'pos_x': nx * playResX,
                    'pos_y': ny * playResY,
                    'pos_x_norm': nx,
                    'pos_y_norm': ny,
                  });
                },
                child: Container(
                  padding: EdgeInsets.all(pad / playResY * h),
                  decoration: BoxDecoration(
                    color: boxColor,
                    borderRadius: BorderRadius.circular(radius),
                    border: selected
                        ? Border.all(color: AppTheme.accent, width: 1.5)
                        : null,
                  ),
                  child: Text(
                    text,
                    textAlign: TextAlign.center,
                    maxLines: (style['max_lines'] as num?)?.toInt() ?? 3,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontFamily: style['font_name']?.toString(),
                      fontSize: fontSize.clamp(10.0, 64.0),
                      fontWeight: bold ? FontWeight.w800 : FontWeight.w500,
                      fontStyle: italic ? FontStyle.italic : FontStyle.normal,
                      letterSpacing:
                          (style['letter_spacing'] as num?)?.toDouble(),
                      height: (style['line_spacing'] as num?)?.toDouble() ?? 1.15,
                      color: primary,
                      shadows: shadows,
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
