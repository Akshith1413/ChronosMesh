import { describe, it, expect } from 'vitest';
import { getServiceColor, getServiceLabel, getConfidenceBadge, withAlpha } from '../utils/colors';

describe('Frontend Utility Tests', () => {
  it('correctly maps known microservice IDs to colors', () => {
    expect(getServiceColor('order-svc')).toBe('#4c6ef5');
    expect(getServiceColor('payment-svc')).toBe('#0fb98a');
    expect(getServiceColor('inventory-svc')).toBe('#f59f00');
    expect(getServiceColor('shipping-svc')).toBe('#8f4cf0');
    expect(getServiceColor('unknown-svc')).toBe('#8b89a8');
  });

  it('derives alpha variants from concrete hex colours', () => {
    expect(withAlpha('#4c6ef5', 0.5)).toBe('rgba(76, 110, 245, 0.5)');
    // Non-hex input is passed through untouched rather than corrupted
    expect(withAlpha('var(--x)', 0.5)).toBe('var(--x)');
  });

  it('formats microservice display labels', () => {
    expect(getServiceLabel('order-svc')).toBe('ORDER');
    expect(getServiceLabel('payment-svc')).toBe('PAYMENT');
    expect(getServiceLabel('inventory-svc')).toBe('INVENTORY');
    expect(getServiceLabel('shipping-svc')).toBe('SHIPPING');
  });

  it('classifies confidence scores into High, Medium, and Low bands', () => {
    const high = getConfidenceBadge(0.95);
    expect(high.label).toBe('High Confidence');
    expect(high.color).toBe('#0fb98a');

    const med = getConfidenceBadge(0.78);
    expect(med.label).toBe('Medium Confidence');
    expect(med.color).toBe('#f59f00');

    const low = getConfidenceBadge(0.42);
    expect(low.label).toContain('Low Confidence');
    expect(low.color).toBe('#f0405f');
  });
});

describe('API Service Contract Validation', () => {
  it('validates auth token storage', async () => {
    const { api } = await import('../services/api');
    api.setToken('test-jwt-token-123');
    expect(api.getToken()).toBe('test-jwt-token-123');

    api.logout();
    expect(api.getToken()).toBeNull();
  });
});
