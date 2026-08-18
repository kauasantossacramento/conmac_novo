import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

def generate_and_convert_vapid_keys():
    # 1. Gera chave privada usando curva P-256 (SECP256R1)
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # 2. Exporta em formato DER (binário cru)
    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # 3. Converte para Base64 URL-safe (sem padding "=")
    private_b64 = base64.urlsafe_b64encode(private_der).decode('utf-8').rstrip("=")
    public_b64 = base64.urlsafe_b64encode(public_der).decode('utf-8').rstrip("=")

    print("VAPID Private Key (Base64 URL-safe):\n", private_b64)
    print("VAPID Public Key (Base64 URL-safe):\n", public_b64)

    # 4. Mostra como ficaria no settings.py
    print("\nCole no settings.py:")
    print(f'WEBPUSH_SETTINGS = {{\n'
          f'    "VAPID_PUBLIC_KEY": "{public_b64}",\n'
          f'    "VAPID_PRIVATE_KEY": "{private_b64}",\n'
          f'    "VAPID_ADMIN_EMAIL": "kaua@conmac.com.br"\n'
          f'}}')

if __name__ == "__main__":
    generate_and_convert_vapid_keys()