"""O mesmo recorte de `etl/cnpj.py` em PySpark, no modo local."""

import json
import shutil
import sys
import time
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

from telecom_analyst.etl import cnpj

CPF = cnpj.CPF_IN_NAME


def read(spark: SparkSession, directory: Path, columns: tuple[str, ...]) -> DataFrame:
    schema = StructType([StructField(column, StringType()) for column in columns])
    return spark.read.csv(str(directory), schema=schema, sep=";", quote='"', escape='"')


def to_date(column: str) -> F.Column:
    return F.to_date(F.col(column), "yyyyMMdd").alias(column)


def run(spark: SparkSession, csvs: Path, providers: Path, output: Path) -> None:
    raw = read(spark, csvs / "estabelecimentos", cnpj.ESTABELECIMENTOS_COLUMNS).cache()
    telecom = F.array(*[F.lit(code) for code in cnpj.TELECOM_CNAES])
    by_cnae = raw.filter(
        F.col("cnae_principal").isin(*cnpj.TELECOM_CNAES)
        | F.arrays_overlap(F.split(F.col("cnae_secundaria"), ","), telecom)
    ).select("cnpj_basico")
    anatel = spark.read.parquet(str(providers)).select(
        F.substring("cnpj", 1, 8).alias("cnpj_basico")
    )
    target = F.broadcast(by_cnae.union(anatel).distinct())

    establishments = raw.join(target, "cnpj_basico", "left_semi").select(
        F.concat("cnpj_basico", "cnpj_ordem", "cnpj_dv").alias("cnpj"),
        "cnpj_basico",
        (F.col("identificador_matriz_filial") == "1").alias("matriz"),
        F.regexp_replace("nome_fantasia", CPF, "").alias("nome_fantasia"),
        "situacao_cadastral",
        to_date("data_situacao_cadastral"),
        "motivo_situacao_cadastral",
        to_date("data_inicio_atividade"),
        "cnae_principal",
        "cnae_secundaria",
        "uf",
        "municipio_tom",
    )
    establishments.write.mode("overwrite").partitionBy("uf").parquet(
        str(output / "estabelecimentos")
    )

    companies = (
        read(spark, csvs / "empresas", cnpj.EMPRESAS_COLUMNS)
        .join(target, "cnpj_basico", "left_semi")
        .select(
            "cnpj_basico",
            F.trim(F.regexp_replace("razao_social", CPF, "")).alias("razao_social"),
            "natureza_juridica",
            F.regexp_replace("capital_social", ",", ".").cast("double").alias("capital_social"),
            "porte_empresa",
        )
    )
    companies.write.mode("overwrite").parquet(str(output / "empresas"))

    partners = (
        read(spark, csvs / "socios", cnpj.SOCIOS_COLUMNS)
        .join(target, "cnpj_basico", "left_semi")
        .select(
            "cnpj_basico",
            "identificador_socio",
            "nome_socio",
            "cnpj_cpf_socio",
            "qualificacao_socio",
            to_date("data_entrada_sociedade"),
        )
    )
    partners.write.mode("overwrite").parquet(str(output / "socios"))

    for table in ("cnaes", "motivos", "municipios", "naturezas", "qualificacoes"):
        read(spark, csvs / table, cnpj.LOOKUP_COLUMNS).write.mode("overwrite").parquet(
            str(output / table)
        )


def main(csvs: Path, providers: Path, output: Path) -> None:
    shutil.rmtree(output, ignore_errors=True)
    spark = (
        SparkSession.builder.master("local[*]")
        .appName("cnpj-telecom")
        .config("spark.driver.memory", "6g")
        .config("spark.sql.ansi.enabled", "false")
        .config("spark.sql.parquet.compression.codec", "zstd")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    started = time.perf_counter()
    run(spark, csvs, providers, output)
    elapsed = time.perf_counter() - started

    rows = {
        table: spark.read.parquet(str(output / table)).count()
        for table in ("estabelecimentos", "empresas", "socios")
    }
    print(json.dumps({"engine": "spark", "seconds": round(elapsed, 1), "rows": rows}))
    spark.stop()


if __name__ == "__main__":
    main(*(Path(argument) for argument in sys.argv[1:4]))
