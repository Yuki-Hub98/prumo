from interiores_banco.versoes import alvo_desfazer, alvo_refazer, ler_operacao, operacao


def test_ler_operacao() -> None:
    assert ler_operacao("desfazer:9") == ("desfazer", 9)
    assert ler_operacao(operacao("reverter", 3)) == ("reverter", 3)
    assert ler_operacao("mover_movel") is None
    assert ler_operacao(None) is None
    assert ler_operacao("desfazer:x") is None
    assert ler_operacao("outra:2") is None


def test_desfazer_e_refazer_em_sequencia() -> None:
    # 1 importar, 2..9 edições, 10 apagou o quarto (o caso real de 2026-11-19)
    ops: dict[int, str | None] = {1: "importar", **{v: "mover_movel" for v in range(2, 10)}}
    ops[10] = "remover_comodo"
    assert alvo_refazer(ops, 10) is None
    assert alvo_desfazer(ops, 10) == 9
    ops[11] = "desfazer:9"  # quarto de volta
    assert alvo_desfazer(ops, 11) == 8  # desfazer de novo: a edição de antes
    assert alvo_refazer(ops, 11) == 10
    ops[12] = "desfazer:8"
    assert alvo_desfazer(ops, 12) == 7
    assert alvo_refazer(ops, 12) == 11  # refaz o último desfazer primeiro (estado 9)
    ops[13] = "refazer:11"
    assert alvo_refazer(ops, 13) == 10  # e depois o primeiro
    assert alvo_desfazer(ops, 13) == 8  # conteúdo = 11 = 9: desfazer volta para 8
    ops[14] = "refazer:10"
    assert alvo_refazer(ops, 14) is None  # tudo refeito
    assert alvo_desfazer(ops, 14) == 9


def test_edicao_nova_zera_o_refazer() -> None:
    ops: dict[int, str | None] = {1: "importar", 2: "mover_movel", 3: "desfazer:1"}
    assert alvo_refazer(ops, 3) == 2
    ops[4] = "mover_movel"
    assert alvo_refazer(ops, 4) is None
    assert alvo_desfazer(ops, 4) == 3


def test_reverter_conta_como_edicao() -> None:
    ops: dict[int, str | None] = {1: "importar", 2: "a", 3: "b", 4: "reverter:1"}
    assert alvo_desfazer(ops, 4) == 3  # desfazer o "voltar para a versão 1"
    assert alvo_refazer(ops, 4) is None


def test_primeira_versao_nao_tem_o_que_desfazer() -> None:
    assert alvo_desfazer({1: "importar"}, 1) is None
    ops: dict[int, str | None] = {1: "importar", 2: "mover_movel", 3: "desfazer:1"}
    assert alvo_desfazer(ops, 3) is None  # já está no conteúdo da primeira
