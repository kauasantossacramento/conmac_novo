# Localização: despesas/management/commands/aprovar_pendentes.py

import re
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone

from despesas.models import Despesa

User = get_user_model()

BOLD   = "\033[1m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"


def cabecalho(texto: str) -> str:
    linha = "─" * (len(texto) + 4)
    return f"\n{BOLD}{CYAN}{linha}\n  {texto}\n{linha}{RESET}"


class Command(BaseCommand):
    help = (
        "Varre despesas e as move em lote alterando seu status. "
        "Permite filtrar por todos, usuários específicos ou mês/ano (data_fato)."
    )

    def handle(self, *args, **options):
        self.stdout.write(cabecalho("Atualização de Despesas em Lote"))

        # 1. Escolha do Novo Status
        self.stdout.write(f"{BOLD}Escolha a ação a ser realizada:{RESET}\n")
        self.stdout.write(f"  {CYAN}1.{RESET} Reverter para {BOLD}PENDENTE{RESET} (Puxa de Pendente de Pagto/Aprovada)")
        self.stdout.write(f"  {CYAN}2.{RESET} Avançar para {BOLD}PENDENTE_PAGTO{RESET} (Puxa apenas de Pendente)")
        self.stdout.write(f"  {CYAN}3.{RESET} Finalizar para {BOLD}APROVADA (Pagas){RESET} (Puxa de Pendente/Pendente de Pagto)")

        while True:
            escolha_status = input(f"\n{BOLD}Opção [1, 2 ou 3]: {RESET}").strip()
            if escolha_status in ("1", "2", "3"):
                break
            self.stdout.write(f"{RED}Opção inválida. Digite 1, 2 ou 3.{RESET}")

        # Trava rigorosa de Origem -> Destino
        if escolha_status == "1":
            novo_status = Despesa.Status.PENDENTE
            status_origem = [Despesa.Status.PENDENTE_PAGTO, Despesa.Status.APROVADA]
        elif escolha_status == "2":
            novo_status = Despesa.Status.PENDENTE_PAGTO
            status_origem = [Despesa.Status.PENDENTE]
        else:
            novo_status = Despesa.Status.APROVADA
            status_origem = [Despesa.Status.PENDENTE, Despesa.Status.PENDENTE_PAGTO]

        despesas = Despesa.objects.filter(status__in=status_origem).select_related("usuario")

        # 2. Escolha do Escopo
        self.stdout.write(f"\n{BOLD}Qual o escopo da atualização?{RESET}\n")
        self.stdout.write(f"  {CYAN}1.{RESET} Todos os registros (Cuidado: puxará histórico antigo)")
        self.stdout.write(f"  {CYAN}2.{RESET} Colaboradores específicos")
        self.stdout.write(f"  {CYAN}3.{RESET} Todos os registros de um Mês/Ano específico (Data do Gasto)")

        while True:
            escolha_escopo = input(f"\n{BOLD}Opção [1, 2 ou 3]: {RESET}").strip()
            if escolha_escopo in ("1", "2", "3"):
                break
            self.stdout.write(f"{RED}Opção inválida. Digite 1, 2 ou 3.{RESET}")

        # 3. Aplicação do Escopo
        if escolha_escopo == "1":
            # Todos os colaboradores
            excluir = input(f"\n{BOLD}Deseja EXCLUIR algum colaborador da operação? [s/N]: {RESET}").strip().lower()
            if excluir in ("s", "sim"):
                usuarios_excluidos = self._selecionar_multiplos_usuarios(acao="EXCLUIR")
                if usuarios_excluidos:
                    despesas = despesas.exclude(usuario__in=usuarios_excluidos)
                    
        elif escolha_escopo == "2":
            # Colaboradores Específicos
            self.stdout.write(f"\n{BOLD}Selecione os colaboradores que deseja INCLUIR:{RESET}")
            usuarios_incluidos = self._selecionar_multiplos_usuarios(acao="INCLUIR")
            if not usuarios_incluidos:
                self.stdout.write(f"\n{YELLOW}Nenhum usuário selecionado. Operação cancelada.{RESET}\n")
                return
            despesas = despesas.filter(usuario__in=usuarios_incluidos)

        elif escolha_escopo == "3":
            # Filtrar por Mês e Ano (agora usando data_fato ao invés de criado_em)
            mes, ano = self._pedir_mes_ano()
            despesas = despesas.filter(data_fato__year=ano, data_fato__month=mes)
            
            self.stdout.write(f"\n{CYAN}Filtro aplicado: Data do Gasto/Ocorrido (data_fato) = {mes:02d}/{ano}{RESET}")

            # Permite exclusão também no filtro por mês
            excluir = input(f"\n{BOLD}Deseja EXCLUIR algum colaborador deste mês? [s/N]: {RESET}").strip().lower()
            if excluir in ("s", "sim"):
                usuarios_excluidos = self._selecionar_multiplos_usuarios(acao="EXCLUIR")
                if usuarios_excluidos:
                    despesas = despesas.exclude(usuario__in=usuarios_excluidos)

        # 4. Checagem de Resultados
        total_despesas = despesas.count()

        if total_despesas == 0:
            self.stdout.write(f"\n{YELLOW}Nenhuma despesa encontrada para os critérios selecionados.{RESET}\n")
            return

        # 5. Exibir Resumo Agrupado
        self._exibir_resumo(despesas, novo_status, total_despesas)

        # 6. Confirmação
        confirmacao = input(
            f"\n{BOLD}Deseja mover {total_despesas} despesa(s) para "
            f"{novo_status}? [s/N]: {RESET}"
        ).strip().lower()

        if confirmacao not in ("s", "sim"):
            self.stdout.write(f"{YELLOW}Operação cancelada.{RESET}\n")
            return

        # 7. Aplicar Atualização
        atualizadas = self._aplicar_atualizacao(despesas, novo_status)

        self.stdout.write(
            f"\n{GREEN}{BOLD}✔ {atualizadas} despesa(s) atualizadas com sucesso para {novo_status}!{RESET}\n"
        )

    # ------------------------------------------------------------------

    def _pedir_mes_ano(self) -> tuple:
        """Pede ao usuário um mês e ano no formato MM/AAAA."""
        while True:
            valor = input(f"\n{BOLD}Digite o mês e ano (MM/AAAA): {RESET}").strip()
            match = re.match(r"^(\d{2})/(\d{4})$", valor)
            if match:
                mes, ano = int(match.group(1)), int(match.group(2))
                if 1 <= mes <= 12:
                    return mes, ano
            self.stdout.write(f"{RED}Formato inválido ou mês incorreto. Use MM/AAAA (ex: 08/2026).{RESET}")

    def _selecionar_multiplos_usuarios(self, acao: str) -> list:
        """Permite buscar e adicionar múltiplos usuários a uma lista."""
        selecionados = []
        
        while True:
            if selecionados:
                nomes_atuais = ", ".join([u.username for u in selecionados])
                self.stdout.write(f"\n  {GREEN}Lista atual para {acao}: {nomes_atuais}{RESET}")
                
            nome = input(f"\n{BOLD}Digite o nome para buscar (ou ENTER vazio para concluir): {RESET}").strip()
            
            if not nome:
                break
                
            usuarios = (
                User.objects.filter(
                    Q(username__icontains=nome)
                    | Q(first_name__icontains=nome)
                    | Q(last_name__icontains=nome)
                )
                .distinct()
                .order_by("username")
            )

            if not usuarios.exists():
                self.stdout.write(f"{YELLOW}Nenhum usuário encontrado para '{nome}'.{RESET}")
                continue

            lista = list(usuarios)
            self.stdout.write(f"\n{BOLD}Usuários encontrados:{RESET}")
            for i, u in enumerate(lista, start=1):
                nome_completo = u.get_full_name() or "—"
                self.stdout.write(f"  {CYAN}{i:>3}.{RESET} {u.username:<30} {nome_completo}")

            escolha = input(f"\n{BOLD}Selecione o número (ou ENTER para cancelar busca atual): {RESET}").strip()
            if not escolha:
                continue

            try:
                idx = int(escolha) - 1
                if 0 <= idx < len(lista):
                    usr = lista[idx]
                    if usr not in selecionados:
                        selecionados.append(usr)
                        self.stdout.write(f"{GREEN}✔ Usuário '{usr.username}' adicionado à lista.{RESET}")
                    else:
                        self.stdout.write(f"{YELLOW}⚠ Usuário já está na lista.{RESET}")
                else:
                    self.stdout.write(f"{RED}Número fora do intervalo.{RESET}")
            except ValueError:
                self.stdout.write(f"{RED}Entrada inválida.{RESET}")

        return selecionados

    def _exibir_resumo(self, despesas, novo_status: str, total_despesas: int) -> None:
        """Exibe o total geral e lista resumida de quantos gastos por colaborador serão afetados."""
        soma_geral = despesas.aggregate(total_valor=Sum('valor'))['total_valor'] or 0

        self.stdout.write(f"\n{BOLD}Resumo da Operação para {CYAN}{novo_status}{RESET}:")
        self.stdout.write("  " + "─" * 70)

        # Agrupa quantidades e valores por usuário
        resumo_usuarios = despesas.values(
            'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            qtd=Count('id'),
            soma=Sum('valor')
        ).order_by('-soma')

        for r in resumo_usuarios:
            nome_completo = f"{r['usuario__first_name']} {r['usuario__last_name']}".strip()
            nome_exibicao = nome_completo if nome_completo else r['usuario__username']
            
            self.stdout.write(
                f"  {nome_exibicao:<35} | {r['qtd']:>3} despesa(s) | R$ {r['soma']:>10.2f}"
            )

        self.stdout.write("  " + "─" * 70)
        self.stdout.write(
            f"  {BOLD}TOTAL GERAL:{RESET} {total_despesas} registros somando {GREEN}R$ {soma_geral:>10.2f}{RESET}\n"
        )

    @transaction.atomic
    def _aplicar_atualizacao(self, despesas, novo_status: str) -> int:
        agora = timezone.now()
        hoje = agora.date()

        # Preenche primeira_analise_em apenas onde ainda é None
        despesas.filter(primeira_analise_em__isnull=True).update(primeira_analise_em=agora)

        # Se for mover direto para APROVADA (paga), garante que a data do pagamento exista
        if novo_status == Despesa.Status.APROVADA:
            despesas.filter(pago_em__isnull=True).update(pago_em=hoje)

        # Atualiza status e flag em lote
        count = despesas.update(
            status=novo_status,
            foi_avaliada=True,
        )
        return count