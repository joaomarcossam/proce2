from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from sistema_logs.models import Logs
from core.models import Projeto, Pesquisador
from sistema_logs.registroLog import RegistroLog

class RegistroLogTestCase(TestCase):
    def setUp(self):
        self.pesquisador = Pesquisador.objects.create(nome="Teste", email="Teste@Teste.com", telefone="123456789")
        self.projeto = Projeto.objects.create(titulo="Projeto Teste", pesquisador=self.pesquisador)

        hoje = timezone.now()

        self.data_a = hoje - timedelta(days=2)
        self.data_b = hoje - timedelta(days=1)
        self.data_c = hoje

        self.log1 = Logs.objects.create(
            nome_log="A",
            processo="proc1",
            parametros_usados={"x": 10},
            projeto=self.projeto,
            concluiu=True,
            horario=self.data_a
        )
        self.log2 = Logs.objects.create(
            nome_log="B",
            processo="proc2",
            parametros_usados={"x": 20, "z": "Hello, World!"},
            projeto=self.projeto,
            concluiu=False,
            msgErro="Falha",
            horario=self.data_b
        )
        self.log3 = Logs.objects.create(
            nome_log="A",
            processo="proc3",
            parametros_usados={"y": 99},
            projeto=None,
            concluiu=True,
            horario=self.data_c
        )

    # Registra

    def teste_registra_cria_log_com_sucesso(self):
        RegistroLog.registra(
            nome_log="Teste",
            processo="processo_x",
            parametros_func={"a": 1, "b": 2},
            projeto=self.projeto
        )

        log = Logs.objects.last()

        self.assertIsNotNone(log)
        self.assertEqual(log.nome_log, "Teste")
        self.assertEqual(log.processo, "processo_x")
        self.assertEqual(log.parametros_usados, {"a": 1, "b": 2})
        self.assertEqual(log.projeto, self.projeto)
        self.assertTrue(log.concluiu)
        self.assertIsNone(log.msgErro)

    def teste_registra_com_erro(self):
        RegistroLog.registra(
            nome_log="FalhaTeste",
            processo="proc_errado",
            parametros_func={"x": 99},
            projeto=None,
            msgErro="Explodiu"
        )

        log = Logs.objects.last()

        self.assertFalse(log.concluiu)
        self.assertEqual(log.msgErro, "Explodiu")
        self.assertEqual(log.nome_log, "FalhaTeste")

    def teste_registra_sem_parametros(self):
        RegistroLog.registra(
            nome_log="SemParams",
            processo="proc_sem",
        )

        log = Logs.objects.last()

        self.assertEqual(log.nome_log, "SemParams")
        self.assertEqual(log.processo, "proc_sem")
        self.assertEqual(log.parametros_usados, None)
        self.assertTrue(log.concluiu)

    def teste_registra_projeto_none(self):
        RegistroLog.registra(
            nome_log="SemProjeto",
            processo="proc_teste",
            projeto=None,
        )

        log = Logs.objects.last()
        self.assertIsNone(log.projeto)

    def teste_registra_cria_horario_automatico(self):
        RegistroLog.registra(
            nome_log="Horario",
            processo="proc_horario",
        )

        log = Logs.objects.last()
        self.assertIsNotNone(log.horario)
    # BuscaLog

    def teste_filtro_nome_log(self):
        resultados = RegistroLog.buscaLog(filtro_nome_log="A")
        self.assertEqual(resultados.count(), 2)

    def teste_filtro_processo(self):
        resultados = RegistroLog.buscaLog(filtro_processo="proc2")
        self.assertEqual(resultados.first(), self.log2)

    def teste_filtro_id(self):
        resultados = RegistroLog.buscaLog(filtro_id=self.log1.id)
        self.assertEqual(resultados.first(), self.log1)

    def teste_filtro_projeto(self):
        resultados = RegistroLog.buscaLog(filtro_projeto=self.projeto)
        self.assertEqual(resultados.count(), 2)

    def teste_filtro_parametros_num(self):
        resultados = RegistroLog.buscaLog(filtro_parametros_func={"x": 10})
        self.assertEqual(resultados.first(), self.log1)

    def teste_filtro_parametros_string(self):
        resultados = RegistroLog.buscaLog(filtro_parametros_func={"z": "Hello, World!"})
        self.assertEqual(resultados.first(), self.log2)

    def teste_filtro_parametros_multiplos_false(self):
        resultados = RegistroLog.buscaLog(filtro_parametros_func={"x": 10, "z": "Hello, World!"})
        self.assertEqual(resultados.count(), 0)

    def teste_filtro_parametros_multiplos_true(self):
        resultados = RegistroLog.buscaLog(filtro_parametros_func={"x": 20, "z": "Hello, World!"})
        self.assertEqual(resultados.count(), 1)

    def teste_filtro_msgErro(self):
        resultados = RegistroLog.buscaLog(filtro_msgErro="Falha")
        self.assertEqual(resultados.first(), self.log2)

    def teste_filtro_concluiu(self):
        resultados = RegistroLog.buscaLog(filtro_concluiu=False)
        self.assertEqual(resultados.first(), self.log2)

    def teste_filtro_data_gt(self):
        resultados = RegistroLog.buscaLog(
            modo_data="gt",
            filtro_data_inicial=self.data_b
        )
        self.assertEqual(resultados.count(), 1)
        self.assertEqual(resultados.first(), self.log3)


    def teste_filtro_data_gte(self):
        resultados = RegistroLog.buscaLog(
            modo_data="gte",
            filtro_data_inicial=self.data_b
        )
        self.assertEqual(resultados.count(), 2)
        self.assertEqual(resultados.first(), self.log2)


    def teste_filtro_data_lt(self):
        resultados = RegistroLog.buscaLog(
            modo_data="lt",
            filtro_data_final=self.data_b
        )
        self.assertEqual(resultados.count(), 1)
        self.assertEqual(resultados.first(), self.log1)


    def teste_filtro_data_lte(self):
        resultados = RegistroLog.buscaLog(
            modo_data="lte",
            filtro_data_final=self.data_b
        )
        # Esperado: log1 (data_a) e log2 (data_b)
        self.assertEqual(resultados.count(), 2)
        self.assertEqual(resultados.first(), self.log1)

    def teste_filtro_data_range(self):
        resultados = RegistroLog.buscaLog(
            modo_data="range",
            filtro_data_inicial=self.data_a,
            filtro_data_final=self.data_b
        )
        self.assertEqual(resultados.count(), 2)

    def teste_filtro_data_date(self):
        resultados = RegistroLog.buscaLog(
            modo_data="date",
            filtro_data_inicial=self.data_b
        )
        self.assertEqual(resultados.first(), self.log2)

    def teste_filtro_data_sem_modo(self):
        resultados = RegistroLog.buscaLog(filtro_data_inicial=self.data_c)
        self.assertEqual(resultados.first(), self.log3)

