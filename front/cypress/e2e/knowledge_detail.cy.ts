describe('知识库详情页异常处理测试', () => {
  beforeEach(() => {
    // 拦截登录并模拟成功
    cy.intercept('POST', '/api/v1/auth/login', {
      statusCode: 200,
      body: {
        access_token: 'fake_token',
        token_type: 'bearer',
        user: { id: 1, username: 'admin', role: 'admin' }
      }
    });

    // 访问登录页并操作
    cy.visit('/auth/login');
    cy.get('input[name="username"]').type('admin');
    cy.get('input[name="password"]').type('Admin@123');
    cy.get('button[type="submit"]').click();
  });

  it('访问不存在的知识库应显示“知识库不存在”提示', () => {
    const nonExistentId = 999;
    
    // 拦截后端返回 404 及统一格式的消息体
    cy.intercept('GET', `/api/v1/knowledge/${nonExistentId}`, {
      statusCode: 404,
      body: {
        code: 404,
        msg: '知识库不存在'
      }
    }).as('getKnowledge');

    // 访问该页面
    cy.visit(`/knowledge/${nonExistentId}`);
    
    // 等待请求完成
    cy.wait('@getKnowledge');

    // 断言页面显示提示
    cy.contains('知识库不存在').should('be.visible');
    cy.contains('返回列表').should('be.visible');
  });

  it('成功加载知识库应显示知识库名称', () => {
    const kbId = 1;
    
    // 模拟成功返回
    cy.intercept('GET', `/api/v1/knowledge/${kbId}`, {
      statusCode: 200,
      body: {
        id: kbId,
        name: '示例知识库',
        document_count: 5,
        total_chunks: 100,
        status: 1
      }
    }).as('getKnowledgeSuccess');

    // 模拟文档列表
    cy.intercept('GET', `/api/v1/documents?*`, {
      statusCode: 200,
      body: {
        items: [],
        total: 0
      }
    }).as('getDocs');

    cy.visit(`/knowledge/${kbId}`);
    
    cy.wait('@getKnowledgeSuccess');
    cy.contains('示例知识库').should('be.visible');
  });
});
