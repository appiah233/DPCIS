// Only resolved by vite.importer.config.ts; never part of the production build.
const session = () => fetch("http://127.0.0.1:8000/__test_session").then((response) => {
  if (!response.ok) throw new Error("Local browser test session unavailable");
  return response.json();
});
export const isNeonAuthConfigured = true;
export const getNeonAuthToken = async () => (await session()).token;
export const getCurrentAuthUser = async () => (await session()).user;
export const signOutNeonAuth = async () => {};
export const signInWithEmail = async () => ({ error: null });
export const signUpWithEmail = async () => ({ error: null });
export const signInWithGoogle = async () => ({ error: null });
const unsupportedAuthFlow = async () => { throw new Error("Auth flow is outside the PDF browser harness"); };
export const requestPasswordCode = unsupportedAuthFlow;
export const resetPasswordWithCode = unsupportedAuthFlow;
export const sendEmailVerificationCode = unsupportedAuthFlow;
export const verifyEmailCode = unsupportedAuthFlow;
