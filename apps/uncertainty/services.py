import math
from decimal import Decimal


class UncertaintyCalculator:
    """GUM-compliant combined uncertainty calculation."""

    def calculate(self, contributors, reference_standard=None):
        """
        contributors: list of dicts with keys:
            value, divisor, sensitivity_coefficient, distribution
        Returns dict with combined_u, expanded_u, k, components
        """
        u_components = []
        for c in contributors:
            value = float(c.get('value') or 0)
            divisor = float(c.get('divisor', 1) or 1)
            ci = float(c.get('sensitivity_coefficient', 1) or 1)
            distribution = c.get('distribution', 'NORMAL')

            if distribution == 'RECTANGULAR':
                divisor = math.sqrt(3)
            elif distribution == 'TRIANGULAR':
                divisor = math.sqrt(6)
            elif distribution == 'U_SHAPED':
                divisor = math.sqrt(2)

            standard_u = (value / divisor) * ci
            u_components.append({
                'name': c.get('name', ''),
                'standard_u': standard_u,
                'u_squared': standard_u ** 2,
            })

        if reference_standard:
            ref_u = float(reference_standard.uncertainty_value)
            u_components.append({
                'name': f'Ref Std: {reference_standard.serial_number}',
                'standard_u': ref_u,
                'u_squared': ref_u ** 2,
            })

        combined_u = math.sqrt(sum(c['u_squared'] for c in u_components))
        k = 2.0  # default k=2 for ~95.45% confidence
        expanded_u = combined_u * k

        return {
            'combined_u': round(combined_u, 10),
            'expanded_u': round(expanded_u, 10),
            'k': k,
            'components': u_components,
        }
