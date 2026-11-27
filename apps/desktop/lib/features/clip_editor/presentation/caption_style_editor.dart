import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import 'caption_style_preview.dart';

/// Editable property panels for a caption style (preset = starting point only).
class CaptionStyleEditor extends StatelessWidget {
  const CaptionStyleEditor({
    super.key,
    required this.style,
    required this.onChanged,
    required this.onResetProperty,
  });

  final Map<String, dynamic> style;
  final ValueChanged<Map<String, dynamic>> onChanged;
  final void Function(String key) onResetProperty;

  void _set(String key, dynamic value) {
    onChanged({...style, key: value});
  }

  @override
  Widget build(BuildContext context) {
    final fontSize = (style['font_size'] as num?)?.toDouble() ?? 48;
    final weight = (style['font_weight'] as num?)?.toInt() ?? 400;
    final textOpacity = (style['text_opacity'] as num?)?.toDouble() ?? 1.0;
    final bgOpacity = (style['background_opacity'] as num?)?.toDouble() ?? 0.0;
    final outline = (style['outline'] as num?)?.toDouble() ?? 0;
    final shadow = (style['shadow'] as num?)?.toDouble() ?? 0;
    final marginV = (style['margin_v'] as num?)?.toDouble() ?? 80;
    final marginL = (style['margin_l'] as num?)?.toDouble() ?? 40;
    final marginR = (style['margin_r'] as num?)?.toDouble() ?? 40;
    final maxWidth = (style['max_width'] as num?)?.toDouble() ?? 1000;
    final padding = (style['padding'] as num?)?.toDouble() ?? 8;
    final letterSpacing = (style['letter_spacing'] as num?)?.toDouble() ?? 0;
    final lineSpacing = (style['line_spacing'] as num?)?.toDouble() ?? 1.0;
    final corner = (style['corner_radius'] as num?)?.toDouble() ?? 0;
    final alignment = (style['alignment'] as num?)?.toInt() ?? 2;
    final animDur = (style['animation_duration'] as num?)?.toDouble() ?? 0.25;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        CaptionStylePreview(
          style: style,
          label: 'Live · ${style['label'] ?? style['preset'] ?? 'style'}',
          height: 120,
          selected: true,
        ),
        const SizedBox(height: 10),
        _section(context, 'Typography'),
        _labeledField(
          'Font family',
          TextFormField(
            initialValue: style['font_name']?.toString() ?? 'Arial',
            decoration: const InputDecoration(isDense: true),
            onChanged: (v) => _set('font_name', v),
          ),
        ),
        Text('Size ${fontSize.round()}'),
        Row(
          children: [
            Expanded(
              child: Slider(
                value: fontSize.clamp(12, 120),
                min: 12,
                max: 120,
                onChanged: (v) => _set('font_size', v.round()),
              ),
            ),
            IconButton(
              tooltip: 'Reset size',
              onPressed: () => onResetProperty('font_size'),
              icon: const Icon(Icons.restart_alt, size: 16),
            ),
          ],
        ),
        DropdownButtonFormField<int>(
          value: weight >= 800
              ? 800
              : weight >= 700
                  ? 700
                  : weight >= 600
                      ? 600
                      : weight >= 500
                          ? 500
                          : 400,
          decoration: const InputDecoration(labelText: 'Weight', isDense: true),
          items: const [
            DropdownMenuItem(value: 400, child: Text('Regular')),
            DropdownMenuItem(value: 500, child: Text('Medium')),
            DropdownMenuItem(value: 600, child: Text('Semibold')),
            DropdownMenuItem(value: 700, child: Text('Bold')),
            DropdownMenuItem(value: 800, child: Text('ExtraBold')),
          ],
          onChanged: (v) {
            if (v == null) return;
            onChanged({
              ...style,
              'font_weight': v,
              'bold': v >= 600 ? 1 : 0,
            });
          },
        ),
        SwitchListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          title: const Text('Italic'),
          value: style['italic'] == true || style['italic'] == 1,
          onChanged: (v) => _set('italic', v ? 1 : 0),
        ),
        Text('Letter spacing ${letterSpacing.toStringAsFixed(1)}'),
        Slider(
          value: letterSpacing.clamp(0, 12),
          min: 0,
          max: 12,
          onChanged: (v) => _set('letter_spacing', v),
        ),
        Text('Line spacing ${lineSpacing.toStringAsFixed(2)}'),
        Slider(
          value: lineSpacing.clamp(0.8, 2.0),
          min: 0.8,
          max: 2.0,
          onChanged: (v) => _set('line_spacing', v),
        ),
        _section(context, 'Position & size'),
        DropdownButtonFormField<int>(
          value: alignment,
          decoration: const InputDecoration(labelText: 'Alignment', isDense: true),
          items: const [
            DropdownMenuItem(value: 1, child: Text('Bottom left')),
            DropdownMenuItem(value: 2, child: Text('Bottom center')),
            DropdownMenuItem(value: 3, child: Text('Bottom right')),
            DropdownMenuItem(value: 5, child: Text('Middle center')),
            DropdownMenuItem(value: 8, child: Text('Top center')),
          ],
          onChanged: (v) {
            if (v == null) return;
            // Clear absolute pos when switching alignment so ASS margins apply
            final next = Map<String, dynamic>.from(style)
              ..['alignment'] = v
              ..remove('pos_x')
              ..remove('pos_y')
              ..remove('pos_x_norm')
              ..remove('pos_y_norm');
            onChanged(next);
          },
        ),
        Text('Vertical margin ${marginV.round()}'),
        Slider(
          value: marginV.clamp(0, 600),
          min: 0,
          max: 600,
          onChanged: (v) => _set('margin_v', v.round()),
        ),
        Text('Left / right margins ${marginL.round()} / ${marginR.round()}'),
        Slider(
          value: marginL.clamp(0, 300),
          min: 0,
          max: 300,
          onChanged: (v) {
            onChanged({
              ...style,
              'margin_l': v.round(),
              'margin_r': v.round(),
            });
          },
        ),
        Text('Max width ${maxWidth.round()} (PlayRes)'),
        Slider(
          value: maxWidth.clamp(200, 1080),
          min: 200,
          max: 1080,
          onChanged: (v) => _set('max_width', v.round()),
        ),
        Text('Padding ${padding.round()}'),
        Slider(
          value: padding.clamp(0, 40),
          min: 0,
          max: 40,
          onChanged: (v) => _set('padding', v.round()),
        ),
        Text(
          'Drag the caption on the preview to set absolute position. '
          'Current: '
          '${style['pos_x'] != null ? 'x=${(style['pos_x'] as num).toStringAsFixed(0)}, y=${(style['pos_y'] as num).toStringAsFixed(0)}' : 'alignment/margins'}',
          style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            onPressed: () {
              final next = Map<String, dynamic>.from(style)
                ..remove('pos_x')
                ..remove('pos_y')
                ..remove('pos_x_norm')
                ..remove('pos_y_norm');
              onChanged(next);
            },
            child: const Text('Clear drag position'),
          ),
        ),
        _section(context, 'Appearance'),
        Text('Text opacity ${(textOpacity * 100).round()}%'),
        Slider(
          value: textOpacity.clamp(0, 1),
          min: 0,
          max: 1,
          onChanged: (v) => _set('text_opacity', v),
        ),
        Text('Background opacity ${(bgOpacity * 100).round()}%'),
        Slider(
          value: bgOpacity.clamp(0, 1),
          min: 0,
          max: 1,
          onChanged: (v) {
            onChanged({
              ...style,
              'background_opacity': v,
              if (v > 0.05) 'border_style': 3,
            });
          },
        ),
        Text('Outline ${outline.round()}'),
        Slider(
          value: outline.clamp(0, 12),
          min: 0,
          max: 12,
          onChanged: (v) => _set('outline', v.round()),
        ),
        Text('Shadow ${shadow.round()}'),
        Slider(
          value: shadow.clamp(0, 12),
          min: 0,
          max: 12,
          onChanged: (v) => _set('shadow', v.round()),
        ),
        Text('Corner radius ${corner.round()} (preview)'),
        Slider(
          value: corner.clamp(0, 32),
          min: 0,
          max: 32,
          onChanged: (v) => _set('corner_radius', v.round()),
        ),
        Wrap(
          spacing: 8,
          children: [
            for (final entry in {
              'White': '#FFFFFF',
              'Yellow': '#FFD400',
              'Cyan': '#00FFFF',
              'Pink': '#FF66FF',
              'Black': '#000000',
            }.entries)
              ActionChip(
                label: Text(entry.key),
                onPressed: () => _set(
                  'primary_colour',
                  CaptionStylePreview.hexToAss(entry.value),
                ),
              ),
          ],
        ),
        _section(context, 'Animations'),
        DropdownButtonFormField<String>(
          value: (style['animation_in']?.toString() ?? 'none'),
          decoration: const InputDecoration(labelText: 'Entrance', isDense: true),
          items: const [
            DropdownMenuItem(value: 'none', child: Text('None')),
            DropdownMenuItem(value: 'fade', child: Text('Fade')),
            DropdownMenuItem(value: 'pop', child: Text('Pop')),
          ],
          onChanged: (v) => _set('animation_in', v ?? 'none'),
        ),
        DropdownButtonFormField<String>(
          value: (style['animation_out']?.toString() ?? 'none'),
          decoration: const InputDecoration(labelText: 'Exit', isDense: true),
          items: const [
            DropdownMenuItem(value: 'none', child: Text('None')),
            DropdownMenuItem(value: 'fade', child: Text('Fade')),
            DropdownMenuItem(value: 'pop', child: Text('Pop')),
          ],
          onChanged: (v) => _set('animation_out', v ?? 'none'),
        ),
        Text('Duration ${animDur.toStringAsFixed(2)}s'),
        Slider(
          value: animDur.clamp(0.05, 1.5),
          min: 0.05,
          max: 1.5,
          onChanged: (v) => _set('animation_duration', v),
        ),
      ],
    );
  }

  Widget _section(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.only(top: 12, bottom: 6),
      child: Text(title, style: Theme.of(context).textTheme.titleSmall),
    );
  }

  Widget _labeledField(String label, Widget child) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          child,
        ],
      ),
    );
  }
}
