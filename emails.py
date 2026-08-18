from despesas.models import Contrato, ContratoEmail  # ajuste o app name se necessário

EMAILS_PADRAO = [
    {'email': 'adriana@conmac.com.br',  'nome_contato': 'Adriana - Diretora - CONMAC',           'principal': False},
    {'email': 'andre@conmac.com.br',    'nome_contato': 'André - Diretor Financeiro - CONMAC',    'principal': False},
    {'email': 'eronssilva@gmail.com',   'nome_contato': 'Erondino - Sócio-Diretor - CONMAC',     'principal': False},
    {'email': 'kaua@conmac.com.br',     'nome_contato': 'Kauã - Analista de Sistemas - CONMAC',  'principal': False},
    {'email': 'edumacedo77@hotmail.com', 'nome_contato': 'Eduardo - Sócio-Diretor',  'principal': False},
]

contratos = Contrato.objects.all()
total_contratos = contratos.count()
criados = 0
ja_existiam = 0

for contrato in contratos:
    for dados in EMAILS_PADRAO:
        obj, created = ContratoEmail.objects.get_or_create(
            contrato=contrato,
            email=dados['email'],
            defaults={'nome_contato': dados['nome_contato'], 'principal': dados['principal']},
        )
        if created:
            criados += 1
        else:
            ja_existiam += 1

print(f"Contratos processados : {total_contratos}")
print(f"Emails inseridos      : {criados}")
print(f"Já existiam (pulados) : {ja_existiam}")