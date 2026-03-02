# Auth — TODO (implement later)

- **Creator signup — already-registered validation**  
  Re-enable the check that returns 409 when phone or email is already registered (in `creator_signup_request`).  
  Code is kept but commented in `auth/controllers.py` with `TODO(auth)`. When re-enabling: uncomment the checks in `creator_signup_request` and decide whether to keep or remove the “existing user → log in and set CREATOR” branch in `creator_verify_otp`.
