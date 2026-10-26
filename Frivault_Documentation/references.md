# Technical References

This file records primary sources consulted while preparing the Frivault
project documents. Re-check the current versions, compatibility and
licenses before implementation or release.

## Python desktop UI

-   pywebview introduction: https://pywebview.idepy.com/en/guide/
-   pywebview usage and JavaScript/Python bridge:
    https://pywebview.idepy.com/en/guide/usage
-   pywebview security guidance:
    https://pywebview.idepy.com/en/guide/security
-   pywebview web engine/runtime notes:
    https://pywebview.idepy.com/en/guide/web_engine
-   Microsoft WebView2 runtime distribution:
    https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution

## Cryptography and key derivation

-   OWASP Cryptographic Storage Cheat Sheet:
    https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
-   Argon2 RFC 9106: https://www.rfc-editor.org/rfc/rfc9106.html
-   argon2-cffi documentation:
    https://argon2-cffi.readthedocs.io/en/stable/
-   Python cryptography documentation:
    https://cryptography.io/en/latest/
-   libsodium secretstream (large authenticated streams):
    https://doc.libsodium.org/secret-key_cryptography/secretstream
-   PyNaCl secretstream binding source:
    https://github.com/pyca/pynacl/blob/main/src/nacl/bindings/crypto_secretstream.py
-   PyNaCl release and license metadata:
    https://pypi.org/project/PyNaCl/
-   argon2-cffi low-level API:
    https://argon2-cffi.readthedocs.io/en/stable/api.html
-   argon2-cffi release and license metadata:
    https://pypi.org/project/argon2-cffi/
-   Google Tink guidance for large files/streams (useful design
    reference; do not assume the library itself is a direct Python
    dependency):
    https://developers.google.com/tink/encrypt-large-files-or-data-streams

## Packaging

-   PyInstaller manual: https://pyinstaller.org/en/stable/

## Important implementation notes

-   These links are technical references, not a security audit.
-   Verify exact dependency versions and licensing before pinning.
-   Use an established streaming authenticated-encryption construction;
    do not invent one from snippets.
-   Check current Python, pywebview, WebView2, cryptography and Argon2
    documentation when implementing.
-   The final vault format requires careful review and testing before
    use with valuable personal data.
