---
name: fluxo-dev
description: "Fluxo de desenvolvimento do Filipe (PO, dev, Reviewer): leia antes de planejar, implementar, revisar, fazer push, merge ou deploy em qualquer projeto de software ou dados dele, ou ao acordar outro bot do time."
---

# Fluxo de desenvolvimento (PO, dev, Reviewer, Filipe)

O Filipe decide. Nenhum bot age sem o gatilho dele indicado abaixo.

**Ferramentas.** Todo trabalho roda no T3 Code (CLI `t3` no WSL) com o Claude, nunca em cloud agents. Modelo: Claude Opus 5.5. Fallback: Grok 4.7 pelo provider Cursor no T3, só quando acabar o limite do Claude Pro.

**Ciclo.**
1. **PO planeja** só quando o Filipe pede, numa thread do T3, sem mexer em código. O plano só vale com aprovação explícita do Filipe.
2. **Dev implementa** só quando o Filipe manda, no chat do dev. Uma issue ou fase por vez, em branch com PR. A ordem de implementar já autoriza commitar, dar push da branch, abrir o PR e analisar o CI. Exceção: no `open-data-platform`, commits convencionais locais direto na `main`, sem push.
3. **Dev entrega** quando o CI do PR foi analisado (no `open-data-platform`, os checks locais): sinaliza ao PO e ao Reviewer que está pronto (o que fez, PR ou hash, CI e checks, pontos em aberto) e avisa o Filipe.
4. **Aprovação dupla:** PO e Reviewer revisam o PR depois desse sinal e aprovam a mesma versão (head do PR; no `open-data-platform`, o hash do último commit local). Qualquer objeção bloqueia.
   - **Rodada** = uma entrega sinalizada. Cada correção é feita com novos commits, CI analisado de novo e novo sinal aos dois. Após duas rodadas de divergência, o Filipe decide.
   - **Mudança pequena** (docs, texto, ajuste de config, bump patch de dependência, ou bugfix contido de até ~50 linhas em até 3 arquivos, sem tocar arquitetura, modelo de dados/schema, auth/segurança, infra/deploy, API pública ou lógica de pipeline; na dúvida, é grande): o dev classifica na entrega; basta o PO aprovar. O Reviewer não revisa, só faz o merge (passo 5).
5. **Publicação:** merge, exclusão de branch e pipelines de CD são do Reviewer, sempre após o sim explícito do Filipe. O Filipe também pode fazer ele mesmo ou ordenar que um bot específico faça; com essa ordem, aquele bot pode. No `open-data-platform`, o push na `main` segue esta mesma regra.
   - Exceção declarada: no `pedsletter`, PRs de conteúdo (`src/content/posts/`) entram pelo merge automático do workflow quando a validação passa.
6. **Pós-merge:** o Reviewer avisa o PO, que atualiza o backlog e propõe o próximo passo ao Filipe.

**Sempre.**
- Mostre ao Filipe os comandos que rodou e as saídas.
- Peça aprovação antes de comando de rede, Git permanente, exclusão de arquivo ou abertura de porta. Já autorizados pela ordem de implementar: commit, push da branch da issue, abertura do PR e leitura do CI pelo dev.
- Só acorde outro bot quando ele precisar agir, quando alguém esperar a resposta dele ou para repassar uma regra do Filipe.
