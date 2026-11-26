# Voice samples

Text Filipe wrote or approved as published. `plain-voice` reads this before editing and follows it over its own rules. Add new samples at the top. Two to five is enough; replace old ones rather than growing the file.

For each sample: where it ran, the language, and the text exactly as published.

What these two share:

- Full sentences joined with "e", "mas", "ou seja", in paragraphs of two to five sentences.
- One story each: the platform's path for a number; a colleague's pipeline from 26h to 6h.
- Few numbers, inside the story.
- What is not done yet is the next step ("Daqui pra frente entram...").
- Technical terms in plain Portuguese with the acronym in parentheses.
- The opening is a question everyone has had, or a scene. The closing is an invitation or a light "né?".

<!-- Template

## <date> · LinkedIn · pt-BR · <topic>

<post text exactly as published>

-->

## LinkedIn · pt-BR · open-data-platform, the path of a number

Todo mundo já viu um número num relatório e pensou: como chegaram nisso?

Estou montando uma plataforma de dados open source para esse número ter um caminho confiável, da origem até quem usa. A ideia é juntar dados de fontes diferentes, guardar os arquivos como chegaram, limpar com regras claras e só publicar o resultado se ele bater com a fonte. Perguntas de negócio, com qualidade e com um caminho que dá para refazer.

O lakehouse já funciona nas três camadas: Bronze, Silver e Gold. Hoje entram o e-commerce da Olist (dataset do Kaggle), uma API de produtos e duas fontes fictícias: um banco de pedidos e eventos de clique num site. Os metadados registram data e origem. Linha com erro fica numa lista de revisão, e o arquivo original continua lá para reprocessar. Bronze guarda, Silver limpa, Gold agrega por domínio de negócio. Testes de reconciliação conferem as camadas entre si e o número final com a origem.

Daqui pra frente entram a orquestração das cargas, o monitoramento, a captura de mudanças do banco (CDC) e o histórico de alterações (SCD). Cada melhoria chega com teste, com o status do projeto e com a decisão de arquitetura escrita.

Se tiver interesse, dá uma olhada no meu repo nos comentários!

## LinkedIn · pt-BR · a colleague's ingestion, 26h to 6h

Vi uma implementação de um colega esses dias que ficou na minha cabeça.

O nosso pipeline rodava extração de dados de um SQL Server legado para nosso ambiente Databricks, em um processo de ingestão diário que levava ~26h para rodar. Ou seja, completamente inviável.

Ele questionou esses números e foi procurar quem estava usando essa fonte, e pasmem, ninguém. Óbvio, ninguém confiava num dado que chegava quase um dia atrasado! Mas foi aí que ele viu o potencial. Não era uma base trivial, era algo que ele enxergou como valor, só não estava sendo bem usado.

Algumas semanas depois, uma orquestração em jobs Databricks e cerca de 30 DAGs no Airflow, e o processo todo roda em 6h, acabando antes do horário comercial começar. Resultado: todo mundo quer nos seus dashboards.

É legal quando a gente identifica valor e entrega uma solução eficaz pro negócio, né?
