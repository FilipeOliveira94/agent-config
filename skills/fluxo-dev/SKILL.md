---
name: fluxo-dev
description: "Fluxo de desenvolvimento do Filipe (PO, dev, Reviewer): leia antes de planejar, implementar, revisar, fazer push, merge ou deploy em qualquer projeto de software ou dados dele, ou ao acordar outro bot do time."
---

# Fluxo de desenvolvimento (PO, dev, Reviewer, Filipe)

O Filipe decide. Nenhum bot age sem o gatilho dele indicado abaixo.

**Ferramentas.** Todo trabalho roda no T3 Code (CLI `t3` no WSL) com o Claude, nunca em cloud agents. Modelo: Claude Opus 5.5. Fallback: Grok 4.7 pelo provider Cursor no T3, só quando acabar o limite do Claude Pro.

**Threads do T3 por issue.**
- **Nome:** toda thread se chama `ISSUEID-descrição concisa da issue` (ex.: `P1-03-cadastro de contas`), definido no `--title` ao abrir. Sem issue (ajuste avulso pedido pelo Filipe), use um id curto que ele reconheça.
- **Uma thread por issue, do plano à implementação:** quando o PO planeja uma issue numa thread, ele passa o id da thread (`mcp:...`) na entrega do plano. O dev responsável manda a implementação nessa mesma thread (`t3 thread send`), saindo do modo plano, para o modelo manter o contexto. Se a thread do plano não tiver a branch da issue, o dev pede ao Claude, na própria thread, para criar a branch antes de mexer no código. As correções das rodadas de revisão também vão nessa thread. Só abra thread nova se não houver thread de plano para a issue.

**Esperar uma thread do T3 terminar (obrigatório).** Logo depois de abrir ou mandar mensagem numa thread pelo CLI `t3`:
1. Chame `t3_thread_wait` do conector `user-t3code` com `environmentId` `3e25557f-d7d0-4911-b1eb-23a277ab952d`, o `threadId` (`mcp:...`) e `timeoutMs: 600000` (10 min, fixo; não use valores maiores).
2. Se voltar timeout sem `next`, chame de novo na hora, com os mesmos parâmetros, até a thread terminar.
3. Só encerre o turno no meio da espera se a resposta trouxer `next`. Nunca encerre o turno dizendo "ainda está rodando" sem uma espera ativa; o Filipe não deve precisar perguntar se acabou.
4. Quando terminar, leia o resultado com `t3 thread show <id>` e entregue logo (passo 3 do ciclo).

**Ciclo.**
1. **PO planeja** só quando o Filipe pede, numa thread do T3, sem mexer em código. O plano só vale com aprovação explícita do Filipe. A entrega do plano cita o id da thread.
2. **Dev implementa** só quando o Filipe manda, no chat do dev, na thread do plano da issue quando houver. Uma issue ou fase por vez, em branch com PR. A ordem de implementar já autoriza commitar, dar push da branch, abrir o PR e analisar o CI. Exceção: no `open-data-platform`, commits convencionais locais direto na `main`, sem push.
3. **Dev entrega** quando o CI do PR foi analisado (no `open-data-platform`, os checks locais): sinaliza ao PO e ao Reviewer que está pronto (o que fez, PR ou hash, CI e checks, pontos em aberto, e se a mudança é pequena ou grande) e avisa o Filipe.
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
