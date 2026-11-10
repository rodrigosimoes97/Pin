Atue como um engenheiro sênior de SEO técnico, Python, automação e desenvolvimento web. Analise e corrija o repositório atual do projeto Health PTG (GitHub: rodrigosimoes97/Pin).

**OBJETIVO:** resolver problemas de indexação do Google, padronizar URLs, corrigir a infraestrutura SEO e elevar a qualidade científica e editorial dos artigos.

### 1. Infraestrutura e SEO técnico
- Audite a geração de URLs, sitemap.xml, robots.txt, canonical, Open Graph, Schema.org e links internos.
- Padronize todas as URLs públicas SEM `.html`, mantendo os arquivos físicos existentes.
- Corrija `site.py`, `_headers` e demais arquivos responsáveis por URLs e metadados.
- Elimine conflitos entre canonical, redirecionamentos e URLs do sitemap.
- Garanta que todas as páginas importantes tenham canonical absoluto apontando para sua própria URL definitiva.
- Corrija links internos, categorias, página inicial e páginas institucionais.
- Garanta que o sitemap contenha somente URLs válidas, indexáveis, canônicas e com resposta HTTP 200.
- Verifique robots.txt, códigos HTTP, redirecionamentos, páginas 404 e metadados duplicados.
- Não crie redirecionamentos desnecessários nem gere cadeias de redirecionamento.

### 2. Qualidade dos artigos e geração Gemini
- Revise `content.py` e o prompt de geração.
- Remova instruções que incentivem experiências pessoais fictícias ou afirmações em primeira pessoa não verificadas.
- Exija conteúdo original, aprofundado, natural e direcionado ao público americano.
- Exija fontes científicas e institucionais verificáveis, priorizando NIH, CDC, FDA, universidades e periódicos científicos.
- Inclua links e referências reais para sustentar afirmações médicas e científicas.
- Nunca invente estudos, autores, instituições, estatísticas ou citações.
- Diferencie evidências consolidadas, estudos preliminares e hipóteses.
- Evite promessas de cura, diagnósticos e recomendações médicas sem fundamentação.
- Implemente validação editorial para detectar conteúdo superficial, repetitivo, impreciso ou sem fontes.
- Melhore títulos, meta descriptions, headings, FAQs, alt text e links internos.
- Garanta transparência editorial, autoria e avisos educacionais adequados.

### 3. Automação e publicação
- Preserve Gemini, Pexels, Pinterest, GitHub Actions e Cloudflare Pages.
- Revise a frequência de publicação para priorizar qualidade sobre quantidade.
- Evite publicar artigos que não passem pelas validações de qualidade.
- Configure UTMs nos links do Pinterest: utm_source=pinterest, utm_medium=organic_social e utm_campaign com slug do artigo.
- Garanta que falhas de geração ou validação não publiquem conteúdo incompleto.

### 4. Testes obrigatórios
Crie ou atualize testes automatizados para verificar:
- Consistência entre URLs, canonical e sitemap.
- Ausência de URLs `.html` no sitemap.
- Respostas HTTP 200 para páginas canônicas.
- Ausência de redirecionamentos indevidos e loops.
- Integridade dos links internos.
- Ausência de páginas importantes bloqueadas por robots.txt.
- Validade do XML do sitemap.
- Ausência de metadados duplicados.
- Validação das referências científicas e estrutura dos artigos.

### 5. Cuidados essenciais
- Não reconstrua o projeto do zero.
- Não remova artigos existentes nem altere seus conteúdos em massa sem necessidade.
- Preserve histórico, funcionalidades, configurações e integrações.
- Não exponha API keys, tokens ou secrets.
- Não faça deploy automático sem minha autorização.
- Faça backup ou trabalhe em uma branch separada antes das alterações.
- Não invente resultados de testes ou verificações externas.

**ENTREGA:** implemente as correções no código, execute os testes, apresente os arquivos modificados, os problemas encontrados, as soluções aplicadas e eventuais pendências que dependam do Google Search Console ou Cloudflare. Priorize uma solução funcional, segura e sustentável para crescimento orgânico nos Estados Unidos.