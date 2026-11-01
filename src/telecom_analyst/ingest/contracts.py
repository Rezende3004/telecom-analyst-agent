"""Contratos de dados de cada fonte. As regras vêm do perfil dos dados reais.

Valores que a fonte pode acrescentar sem aviso, como novas tecnologias, ficam sem lista
fechada para não derrubar o job mensal. Listas fechadas marcam o que deve parar o pipeline
até alguém olhar.
"""

import pandera.polars as pa
import polars as pl
from pandera.api.polars.types import PolarsData

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]  # fmt: skip

MUNICIPIO_IBGE = r"^[0-9]{7}$"
# Desde julho de 2026 a Receita emite CNPJ alfanumérico: nunca trate como número.
CNPJ = r"^[0-9A-Z]{14}$"
CNPJ_BASICO = r"^[0-9A-Z]{8}$"
# CPF completo que a Receita embute na razão social de MEIs. Não pode sair do staging.
SEM_CPF = r"^[^0-9]*([0-9]{1,10}[^0-9]+)*[0-9]{0,10}$"
# Boa Esperança do Norte (MT) foi criado depois do Censo 2022 e não tem dados censitários.
MAX_MUNICIPIOS_SEM_CENSO = 1
# Um CNPJ veio sem empresa, grupo e porte em 540 linhas de 2026-01 a 2026-03. As linhas ficam,
# porque o total oficial conta esses acessos.
MAX_LINHAS_SEM_CADASTRO = 1000

MEIOS_ACESSO = [
    "Cabo Coaxial",
    "Cabo Metálico",
    "Fibra",
    "Híbrido",
    "Indeterminado",
    "LTE",
    "Outra",
    "Rádio",
    "Satélite",
]
FAIXAS_VELOCIDADE = [
    "0Kbps a 512Kbps",
    "0Kbps a 64Kbps",
    "12Mbps a 34Mbps",
    "2Mbps a 12Mbps",
    "2Mbps a 34Mbps",
    "512kbps a 2Mbps",
    "64Kbps a 512Kbps",
    "> 34Mbps",
]


class Acessos(pa.DataFrameModel):
    """Uma linha do CSV longo da Anatel. A chave se repete: some, nunca deduplique."""

    ano: pl.Int16 = pa.Field(ge=2007)
    mes: pl.Int8 = pa.Field(ge=1, le=12)
    grupo_economico: str = pa.Field(nullable=True)
    empresa: str = pa.Field(nullable=True)
    cnpj: str = pa.Field(str_matches=CNPJ)
    porte: str = pa.Field(nullable=True, isin=["Grande Porte", "Pequeno Porte"])
    uf: str = pa.Field(isin=UFS)
    municipio: str
    municipio_ibge: str = pa.Field(str_matches=MUNICIPIO_IBGE)
    faixa_velocidade: str = pa.Field(isin=FAIXAS_VELOCIDADE)
    # Só existe desde 2021. Há valores absurdos declarados, então só exigimos que seja positiva.
    velocidade_mbps: float = pa.Field(nullable=True, gt=0)
    tecnologia: str
    meio_acesso: str = pa.Field(isin=MEIOS_ACESSO)
    tipo_pessoa: str = pa.Field(nullable=True)
    tipo_produto: str = pa.Field(nullable=True)
    acessos: int = pa.Field(gt=0)

    class Config:
        strict = True

    @pa.dataframe_check
    @classmethod
    def poucas_linhas_sem_cadastro(cls, data: PolarsData) -> bool:
        missing = data.lazyframe.select(pl.col("empresa").null_count()).collect().item()
        return bool(missing <= MAX_LINHAS_SEM_CADASTRO)


class TotalMensal(pa.DataFrameModel):
    ano: pl.Int16 = pa.Field(ge=2007)
    mes: pl.Int8 = pa.Field(ge=1, le=12)
    acessos: int = pa.Field(gt=0)

    class Config:
        strict = True


class Densidade(pa.DataFrameModel):
    ano: pl.Int16 = pa.Field(ge=2007)
    mes: pl.Int8 = pa.Field(ge=1, le=12)
    uf: str
    municipio: str
    municipio_ibge: str = pa.Field(str_matches=MUNICIPIO_IBGE)
    densidade: float = pa.Field(nullable=True, ge=0)
    nivel_geografico: str

    class Config:
        strict = True


class Municipio(pa.DataFrameModel):
    municipio_ibge: str = pa.Field(str_matches=MUNICIPIO_IBGE, unique=True)
    municipio: str
    uf: str = pa.Field(isin=UFS)
    uf_nome: str
    regiao: str
    populacao: int = pa.Field(gt=0)
    populacao_ano: int
    domicilios: int = pa.Field(nullable=True, gt=0)
    domicilios_ano: int
    pib_mil_reais: float = pa.Field(nullable=True, gt=0)
    pib_ano: int
    renda_per_capita: float = pa.Field(nullable=True, gt=0)
    renda_ano: int

    class Config:
        strict = True

    @pa.dataframe_check
    @classmethod
    def poucos_municipios_sem_censo(cls, data: PolarsData) -> bool:
        missing = data.lazyframe.select(pl.col("domicilios").null_count()).collect().item()
        return bool(missing <= MAX_MUNICIPIOS_SEM_CENSO)


class EstabelecimentoTelecom(pa.DataFrameModel):
    cnpj: str = pa.Field(str_matches=CNPJ, unique=True)
    cnpj_basico: str = pa.Field(str_matches=CNPJ_BASICO)
    matriz: bool
    nome_fantasia: str = pa.Field(nullable=True, str_matches=SEM_CPF)
    situacao_cadastral: str = pa.Field(isin=["01", "02", "03", "04", "08"])
    data_situacao_cadastral: pl.Date = pa.Field(nullable=True)
    motivo_situacao_cadastral: str = pa.Field(nullable=True)
    data_inicio_atividade: pl.Date = pa.Field(nullable=True)
    cnae_principal: str = pa.Field(str_matches=r"^[0-9]{7}$")
    cnae_secundaria: str = pa.Field(nullable=True)
    uf: str = pa.Field(nullable=True)
    municipio_tom: str = pa.Field(nullable=True)

    class Config:
        strict = True


class EmpresaTelecom(pa.DataFrameModel):
    cnpj_basico: str = pa.Field(str_matches=CNPJ_BASICO, unique=True)
    razao_social: str = pa.Field(nullable=True, str_matches=SEM_CPF)
    natureza_juridica: str = pa.Field(nullable=True)
    capital_social: float = pa.Field(nullable=True, ge=0)
    porte_empresa: str = pa.Field(nullable=True)

    class Config:
        strict = True


class SocioTelecom(pa.DataFrameModel):
    cnpj_basico: str = pa.Field(str_matches=CNPJ_BASICO)
    identificador_socio: str = pa.Field(isin=["1", "2", "3"])
    nome_socio: str = pa.Field(nullable=True)
    cnpj_cpf_socio: str = pa.Field(nullable=True)
    qualificacao_socio: str = pa.Field(nullable=True)
    data_entrada_sociedade: pl.Date = pa.Field(nullable=True)

    class Config:
        strict = True
