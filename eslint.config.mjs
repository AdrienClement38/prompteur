import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["static/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: { ...globals.browser },
    },
    rules: {
      "no-unused-vars": ["error", { args: "after-used", caughtErrors: "none" }],
      // Depuis que le prompteur affiche du texte MIS EN FORME, la seule garantie
      // qu'aucun balisage venu de l'exterieur ne soit execute est de n'en jamais
      // construire. On cree donc des elements et on ecrit du textContent.
      // Interdit ici plutot que releve a la relecture : un oubli ne se voit pas.
      "no-restricted-properties": [
        "error",
        { property: "innerHTML", message: "Construire les éléments et utiliser textContent." },
        { property: "outerHTML", message: "Construire les éléments et utiliser textContent." },
        { property: "insertAdjacentHTML", message: "Utiliser append() avec des éléments." },
      ],
    },
  },
];
