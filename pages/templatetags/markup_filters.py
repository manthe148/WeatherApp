# pages/templatetags/markup_filters.py
import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='markdown_to_html')
def markdown_to_html(text):
    if not text:
        return ""
    # Convert markdown to HTML using a few useful extensions
    # 'extra': Adds features like tables, fenced code blocks, abbreviations, etc.
    # 'nl2br': Converts newlines to <br> tags (like Markdown normally does).
    # 'sane_lists': For more predictable list rendering.
    html = markdown.markdown(text, extensions=['extra', 'nl2br', 'sane_lists'])
    # Mark the HTML as safe to prevent Django from auto-escaping it
    return mark_safe(html)
