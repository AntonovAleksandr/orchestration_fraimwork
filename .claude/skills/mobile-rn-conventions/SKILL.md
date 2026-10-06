---
name: mobile-rn-conventions
description: Use when writing or reviewing TypeScript/TSX code for the Gloria Jeans mobile app. Covers code style, styled-components patterns, when to put code in ui-kit vs packages/gj, env-flavor handling, API type sourcing from mobapp-api-types, native bridge etiquette, common React Native pitfalls. Pairs with `pattern-development-mobile` for structured development.
---

# Mobile RN Conventions

**See also:** [`pattern-development-mobile.md`](../pattern-development-mobile.md) — the mandatory 7-step pattern for writing React Native features with platform awareness.

Guidelines for writing code in `platform/mobile-app/gj-app/`.

## Where does code live?

| What | Where |
|------|-------|
| Reusable visual primitive (Button, Modal, Card, Input) | `packages/ui-kit/components/` |
| Design tokens (colors, spacing, typography) | `packages/ui-kit/styles/`, `packages/ui-kit/constants/` |
| Static asset (icon, image, font) | `packages/ui-kit/assets/` |
| Screen / feature-level component | `packages/gj/src/` (typically `screens/`, `features/`, `modules/`) |
| Navigation config | `packages/gj/src/navigation/` (or similar) |
| API call / network logic | `packages/gj/src/api/` or `services/` (check existing pattern) |
| API contract type (request/response shapes) | `mobapp-api-types/` |
| Hook | `packages/gj/src/hooks/` (or co-located near consumer) |
| Native bridge | `packages/gj/ios/` or `android/` + thin JS wrapper in `src/` |
| Payment-related | use `rn-yookassa-sdk` exports |

**Rule of thumb:** anything app-specific lives in `packages/gj/`. Anything that could be reused by another app (hypothetical) lives in `ui-kit`.

## Styling — styled-components

```tsx
// Good
import styled from 'styled-components/native';

const Container = styled.View`
  padding: 16px;
  background-color: ${({theme}) => theme.colors.background};
`;

// Bad — inline styles bypass the design system
<View style={{padding: 16, backgroundColor: '#fff'}} />
```

- Use ui-kit's `theme` / styled-components theme when available
- For one-off layouts, still prefer a styled component over inline styles for consistency

## TypeScript

- `strict: true` (or close to it) — no `any` without good reason
- Types from `mobapp-api-types` for API contracts — don't redefine
- Co-locate component prop types: `type Props = { ... }` above the component
- For complex types, export from a `types.ts` next to the consumer
- Use type-only imports where possible: `import type { Foo } from '...'`

## Env-flavor awareness

Three flavors: `development`, `staging`, `production`. Behavior must match:
- API endpoints — different per flavor (in `.env.*`)
- Feature flags — sometimes flavor-gated
- Analytics / crash reporting — usually disabled in dev

When writing flavor-aware code:
```tsx
import Config from 'react-native-config'; // or whatever the project uses
const apiUrl = Config.API_URL; // resolved from .env.<flavor>
```

Never hardcode URLs/keys. Always source from `.env.<flavor>`.

## React Native specifics

- **Use `TouchableOpacity`/`Pressable`** for touch targets — never `<div onClick>`-equivalent
- **`KeyboardAvoidingView`** for input screens on iOS
- **`SafeAreaView`** wraps screen roots that have content near edges
- **Lists**: prefer `FlatList`/`SectionList` over `ScrollView` for >10 items
- **Images**: `<Image source={require('...')} />` for static, `{ uri: '...' }` for remote
- **Platform-specific code**: `Platform.OS === 'ios' ? ... : ...` OR file extension `.ios.tsx` / `.android.tsx`

## State management

Check existing patterns first (`grep -rn "createStore\|atom\|create(\|useContext" platform/mobile-app/gj-app/packages/gj/src/`). Common in RN: Redux Toolkit, Zustand, MobX, React Query for server state. Don't introduce a new state lib.

## Performance gotchas

- Memoize expensive children with `React.memo`
- `useCallback` for callbacks passed to `FlatList` items
- Avoid creating styled-components inside render
- `react-native-fast-image` is common for images on lists (check deps)
- Heavy work → off the JS thread (use libraries with native impl)

## Patches (patch-package)

When upstream lib has a bug or missing feature:
1. Edit `node_modules/<lib>/...`
2. `npx patch-package <lib>` — generates patch in `patches/` (or `packages/gj/patches/` depending on where the package is)
3. Commit the patch file
4. `patch-package` runs in `postinstall` to re-apply

Don't fork the lib unless absolutely necessary.

## Native code etiquette

- Edit `android/` / `ios/` ONLY when:
  - A config plugin / JS-level setting can't achieve the goal
  - Adding a permission, URL scheme, deep link, etc.
- Always read the entire file before editing — native files have load-bearing whitespace and order
- For dependencies, prefer adding via JS package + auto-link over manual native integration

## Don't

- Add deps to the root `package.json` — they go into the relevant workspace
- Mix yarn + npm — yarn-only project
- Bypass `patch-package` by editing `node_modules/` without patching
- Skip `yarn lint` and `yarn gj:ts` before committing
- Hardcode flavor-specific values
- Edit `Info.plist` / `AndroidManifest.xml` without explaining why in a comment

## When unsure

- Check existing similar code first (`grep` for analogous patterns in `packages/gj/src/`)
- Refer to `mobile-stack-anatomy` skill for layout
- Refer to `mobile-build-commands` skill for commands
- Delegate to `mobile-navigator` for "where is X" questions
