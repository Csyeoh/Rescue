import { LightingEffect, AmbientLight, DirectionalLight } from '@deck.gl/core';

/**
 * createLightingEffect
 * 
 * Returns a DeckGL LightingEffect rig tailored for either Day or Night operations.
 * 
 * @param isNight - If true, applies high-contrast "Night Ops" lighting.
 */
export function createLightingEffect(isNight: boolean) {
  const ambientLight = new AmbientLight({
    color: [255, 255, 255],
    intensity: isNight ? 0.35 : 1.2, // Boosted ambient to fill harsh shadows
  });

  const sunLight = new DirectionalLight({
    color: isNight ? [100, 130, 255] : [255, 245, 220], 
    intensity: isNight ? 0.3 : 1.0,                  // Lowered key intensity for softer feel
    direction: [-1, -1, -6],                          // Slightly more top-down for broader coverage
  });

  const rimLight = new DirectionalLight({
    color: isNight ? [0, 240, 255] : [200, 200, 255], 
    intensity: isNight ? 0.6 : 0.3,                 
    direction: [1, 1, -1],
  });

  return new LightingEffect({
    ambientLight,
    sunLight,
    rimLight,
  });
}
