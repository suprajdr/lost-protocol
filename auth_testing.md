# Authentication testing notes

The application uses Supabase Auth for volunteer and admin operators and signed server-issued sessions for teams. No test credentials were created in this build. Use the Supabase dashboard to create an operator and seed a team before testing successful authenticated flows.

Safe unauthenticated checks:
- `POST /api/team/login` rejects invalid credentials with 401.
- `/api/control/event` rejects missing or expired operator access tokens.
- `/api/control/volunteer` rejects missing or expired operator access tokens.