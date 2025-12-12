from time import sleep
from enum import StrEnum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from core.models import Projeto
from sistema_logs.models import Logs

"""
TODO:
    Alterar o código para Português
"""


apreciacao_map = {
    'PO': 'Projeto Original de Centro Coordenador',
    'E': 'Emenda de Centro Coornedaor',
    'N': 'Notificação de Centro Coordenador',
    'POp': 'Projeto Original de Centro Participante',
    'Ep': 'Emenda de Centro Participante',
    'Np': 'Notificação de Centro Participante',
    'POc': 'Projeto Original de Centro Coparticipante',
    'Ec': 'Emenda de Centro Coparticipante',
    'Nc': 'Notificação de Centro Coparticipante'
}

class EnumSituacao(StrEnum):
    PENDENTE = "Relatoria Recusada"
    APROVADO = "Relatoria Aprovada"
    REPROVADO = "Em relatoria"

class PlataformaBrasilService:
    base_url = "https://plataformabrasil.saude.gov.br/"
    instance = None

    def __init__(self, headless = True):
        chrome_options = Options()
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        if headless:
            chrome_options.add_argument("--headless")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.logged = False
        self.projects = None
        self.user_email = None
        self.user_password = None

    @classmethod
    def init(cls, headless = True):
        if not cls.instance:
            cls.instance = PlataformaBrasilService(headless)
            cls.instance.open().check_alerts()

        return cls.instance

    def open(self, url = base_url):
        self.instance.driver.get(url)
        return self
    
    def open_local(self, path = base_url):
        from pathlib import Path
        self.driver.get(Path(path).as_uri())
        return self
    
    def check_alerts(self):
        wait = WebDriverWait(self.driver, 3)
       
        try:
            modal = wait.until(
                EC.presence_of_element_located(
                    (By.ID, "modalMsgContainer")
                )
            )
            
            msg_body = modal.find_element(By.CLASS_NAME, "rich-mpnl-body")
        
            print(msg_body.text)
            botao_fechar = modal.find_element(By.ID, "formModalMensagemAviso:botaoFecharModal")
            botao_fechar.click()
            wait.until(EC.invisibility_of_element_located((By.ID, "modalMsg")))
        
            return self

        except TimeoutException:
            print("Timeout")
            return self

        except Exception as e:
            print("Modal nao encontrado.")
            print(e)
            return self

    def login(self, email, password):
        if not (self.user_email and self.user_password):
            print("As credenciais devem ser informadas antes da chamada para o serviço.")
            return self
        
        try:
            email_input = self.driver.find_element(By.ID, "j_id19:email")
            password_input = self.driver.find_element(By.ID, "j_id19:senha")
            login_button = self.driver.find_element(By.CSS_SELECTOR, '[value="LOGIN"]')

            email_input.send_keys(email)
            password_input.send_keys(password)
            login_button.click()
            self.logger = True

            if self.driver.find_element(By.ID, "detalheUsuario"):
                print("Login sucedido")
                self.logged = True

            sleep(5)

            return self
        
        except NoSuchElementException:
            print("Falha no login na Plataforma Brasil")
            
            try:
                message = self.driver.find_element(By.ID, "j_id323:idTituloBloqueio_body")
                inner_body = message.find_elements(By.TAG_NAME, "td")
                for td in inner_body:
                    print(f"{td.text}")
                return self
            
            except:
                print("Nao foi possivel encontrar a mensagem de bloqueio")
                sleep(5)
                
        except Exception as e:
            return self
    
    def search_plubic_by_name(self, name):
        search_menu_button = self.driver.find_element(By.CSS_SELECTOR, "a.pesquisas.das-texto.formatoGG")
        search_menu_button.click()

        search_name_input = self.driver.find_element(By.NAME, "formPesquisarProjPesquisa:j_id71")
        search_name_input.send_keys(name)
        
        
        search_action_button = self.driver.find_element(By.ID, "formPesquisarProjPesquisa:idBtnPesquisar")
        search_action_button.click()

        sleep(60)

        table = self.driver.find_element(By.ID, "formPesquisarProjPesquisa:tabelaResultado:tb")
        row = table.find_elements(By.TAG_NAME, "tr")

        for tr in row:
            cells = tr.find_elements(By.TAG_NAME, "td")
            title = cells[0].text
            author = cells[1].text
            unidade = cells[2].text
            print(f"title: {title}\nauthor: {author}\nunidade: {unidade}\n--------------------")

        return self
    
    def fetch_projects_form_table(self):
        if not self.logged:
            self.login(self.user_email, self.user_password)

        field_map = {
            'apreciacao': 0,
            'tipo': 1,
            'caae': 2,
            'pesquisador': 3,
            'versao': 4,
            'data_aceite': 5,
            'data_ultima_submissao': 6,
            'data_ultima_modificacao': 7,
            'data_primeira_submissao': 8,
            'relator': 9,
            'situacao': 10,
            'nota_tecnica': 11,
            'acao': 12
        }

        table = self.driver.find_element(By.ID, "formConsultarProtocoloPesquisa:tabelaResultado:tb")
        if not table:
            print("Tabela nao encontrada")
            return self
        rows = table.find_elements(By.TAG_NAME, "tr")
        row_count = len(rows)


        for i in range(len(row_count)):
            try:
                table = self.driver.find_element(By.ID, "formConsultarProtocoloPesquisa:tabelaResultado:tb")
                rows = table.find_elements(By.TAG_NAME, "tr")

                row = rows[i]
                cells = row.find_elements(By.TAG_NAME, "td")
                if not cells or len(cells) <= 12:
                    continue

                caae = cells[field_map['caae']].text
                pesquisador = cells[field_map['pesquisador']].text
                data_parecer = cells[field_map['data_ultima_modificacao']].text
                parecer = cells[field_map['situacao']].text
                relator = cells[field_map['relator']].text
                data_aprovacao = None

                if parecer == EnumSituacao.APROVADO:
                    data_aprovacao = cells[field_map['data_ultima_modificacao']].text

            
                detalhes = cells[field_map['acao']].find_elements(By.TAG_NAME, "a")[0]
                detalhes.click()
                sleep(1)

                (
                    self.driver
                        .find_element(By.ID, "idPanelDetalharPesquisador")
                        .find_elements(By.TAG_NAME, "a")[0]
                        .click
                )
                
                email_pesquisador = self.driver.find_element(
                    By.XPATH,
                    "//td[b[normalize-space()='E-mail:']]"
                ).text.split("E-mail:")[1].strip()

                telefone_pesquisador = self.driver.find_element(
                    By.XPATH,
                    "//td[b[normalize-space()='Telefone:']]"
                ).text.split("Telefone:")[1].strip()

                self.driver.back()
                sleep(1)

                Projeto.objects.create(
                    caae=caae,
                    pesquisador=pesquisador,
                    data_parecer=data_parecer,
                    parecer=parecer,
                    relator=relator,
                    data_aprovacao=data_aprovacao,
                    email_pesquisador=email_pesquisador,
                    telefone_pesquisador=telefone_pesquisador
                )
                
            except NoSuchElementException as e:
                print(f"Elemento nao encontrado: {e}")
                continue

            except Exception as e:
                print(f"Falha ao ler informações do projetos")
    
        return self
    
    def receber_credenciais(self, email, senha):
        self.user_email = email
        self.user_password = senha
        return self