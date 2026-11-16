"""Opción de Apariencia para mostrar animaciones aunque el sistema pida reducir el movimiento."""
import importlib.util
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('generar_movimiento_forzado', ROOT / 'scripts' / 'generar_movimiento_forzado.py')
generador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generador)


class ForcedMotionCssTests(SimpleTestCase):
    def test_generated_css_is_up_to_date(self):
        # Si falla: ejecutar «python scripts/generar_movimiento_forzado.py» después de cambiar una animación.
        self.assertEqual(generador.OUTPUT.read_text(encoding='utf-8'), generador.generate())

    def test_every_generated_rule_only_applies_when_the_option_is_on(self):
        css = re.sub(r'/\*.*?\*/', '', generador.generate(), flags=re.S)
        preludes = [p.strip() for p in re.findall(r'(?:^|[{};])\s*([^{};]+?)\s*\{', css)]
        # @media, @view-transition y similares no son selectores; sus reglas internas sí se revisan.
        style_rules = [s.strip() for p in preludes if not p.startswith('@') for s in p.split(',\n')]
        self.assertTrue(style_rules)
        for selector in style_rules:
            self.assertTrue(selector.startswith(('html[data-motion-force="on"]', ':root[data-motion-force="on"]')), selector)

    def test_selectors_are_scoped_without_breaking_html_and_pseudo_elements(self):
        self.assertEqual(generador._scope('html:not([data-motion="off"]) .toast'),
                         'html[data-motion-force="on"]:not([data-motion="off"]) .toast')
        self.assertEqual(generador._scope('::view-transition-old(root)'),
                         'html[data-motion-force="on"]::view-transition-old(root)')
        self.assertEqual(generador._split_selectors('.a, :is(.b, .c) .d'), ['.a', ':is(.b, .c) .d'])


class ForcedMotionPreferenceTests(TestCase):
    def test_appearance_offers_the_option_and_the_page_loads_the_css(self):
        user = get_user_model().objects.create_user(username='titular_movimiento')
        self.client.force_login(user)
        response = self.client.get(reverse('apariencia'))
        self.assertContains(response, 'name="forceMotion"')
        self.assertContains(response, 'Mostrar animaciones aunque el sistema pida reducir el movimiento')
        self.assertContains(response, 'css/movimiento-forzado.css')
