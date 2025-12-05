from typing import Any, Optional
from django.utils.dateparse import parse_datetime

from sistema_logs.models import Logs
from core.models import Projeto

class RegistroLog:
    @staticmethod
    def registra(nome_log: str,
                 processo: str, 
                 parametros_func: Optional[dict[str, Any]] = None, 
                 projeto: Optional[Projeto] = None, 
                 msgErro: Optional[str] = None):
        concluiu = msgErro is None
        Logs.objects.create(
                nome_log=nome_log,
                processo=processo,
                parametros_usados=parametros_func,
                projeto=projeto,
                concluiu=concluiu,
                msgErro=msgErro
            )
        
    @staticmethod
    def buscaLog(
        filtro_nome_log: str = None,
        filtro_processo: str = None,
        filtro_parametros_func: dict[str, Any] | None = None,
        filtro_projeto: Projeto | None = None,
        filtro_msgErro: str | None = None,
        filtro_concluiu: bool | None = None,
        filtro_id: int | None = None,
        filtro_data_inicial = None,
        filtro_data_final  = None,
        modo_data: str | None = None):

        filtros = {}

        if filtro_nome_log is not None:
            filtros["nome_log"] = filtro_nome_log

        if filtro_processo is not None:
            filtros["processo"] = filtro_processo

        if filtro_projeto is not None:
            filtros["projeto"] = filtro_projeto

        if filtro_msgErro is not None:
            filtros["msgErro"] = filtro_msgErro

        if filtro_concluiu is not None:
            filtros["concluiu"] = filtro_concluiu

        if filtro_id is not None:
            filtros["id"] = filtro_id

        if filtro_parametros_func is not None:
            for chave, valor in filtro_parametros_func.items():
                filtros[f"parametros_usados__{chave}"] = valor

        # Coloca string em datetime
        if isinstance(filtro_data_inicial, str):
            filtro_data_inicial = parse_datetime(filtro_data_inicial)

        if isinstance(filtro_data_final, str):
            filtro_data_final = parse_datetime(filtro_data_final)

        # Aplica filtros de data
        if modo_data == "gt" and filtro_data_inicial:
            filtros["horario__gt"] = filtro_data_inicial

        elif modo_data == "gte" and filtro_data_inicial:
            filtros["horario__gte"] = filtro_data_inicial

        elif modo_data == "lt" and filtro_data_final:
            filtros["horario__lt"] = filtro_data_final

        elif modo_data == "lte" and filtro_data_final:
            filtros["horario__lte"] = filtro_data_final

        elif modo_data == "range" and filtro_data_inicial and filtro_data_final:
            filtros["horario__range"] = (filtro_data_inicial, filtro_data_final)

        elif modo_data == "date" and filtro_data_inicial:
            # Ignora horas
            filtros["horario__date"] = filtro_data_inicial.date()
        elif filtro_data_inicial:
            filtros["horario"] = filtro_data_inicial

        return Logs.objects.filter(**filtros)