export const ENGRAVER_TEXT = `
Is anyone else weirded out by the huge amount of sexual/romantic things that get posted about in games?
My group has been playing for over ten years, and not once has a single one of our characters gotten into any kind of sexual or romantic situation. I can't even imagine having an NPC described to me and thinking 'yes, I am going to roleplay hitting on this character, with my old friend the DM playing the person I am hitting on'.
Maybe playing with people I've known for a long time makes it weirder- I know a lot of people are playing online with strangers, maybe that has a different kind of vibe to it. I did once play with people from work and the DM did make it sexually weird at one point- a lot of what I see in this category is actually on r/rpghorrorstories, and this encounter belongs there too. But in a game about fantasy and monsters and treasure and dungeons, sex and romance is for me an instant game killer. It makes it super weird and uncomfortable. I can see that there is a big difference between someone doing what their character would do, and someone using the game to act out bizarre fantasies, but even the former I woud find uncomfortable to sit through.
People play how they play and like what they like, maybe this comes down to people enjoying the roleplay element a lot more than the stats and numbers and combat element. I can't be the only one who is 100% put off the game by any sex and romance. Monsters and dungeons for me please. Does anyone else have absolutely none of this in their games?
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.`;

// Shared geometry keeps the server-rendered field aligned with the canvas.
export const ENGRAVER_GRID = {
  fontSize: 10,
  cellWidth: 6.4,
  lineHeight: 12.5,
  baseline: 9.625,
  columns: 128,
  rows: 32,
};
const normalizedText = ENGRAVER_TEXT.replace(/\s+/g, " ").trim() + " ";
export const ENGRAVER_TILE = Array.from(
  { length: ENGRAVER_GRID.rows },
  (_, row) => Array.from(
    { length: ENGRAVER_GRID.columns },
    (_, column) => normalizedText[(row * ENGRAVER_GRID.columns + column) % normalizedText.length],
  ).join(""),
);
