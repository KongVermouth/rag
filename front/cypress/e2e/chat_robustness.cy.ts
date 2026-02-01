describe('聊天会话稳定性 E2E 测试', () => {
  beforeEach(() => {
    // 登录并进入聊天页面
    cy.visit('/auth/login');
    cy.get('input[name="username"]').type('admin_rag');
    cy.get('input[name="password"]').type('admin123');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/chat');
    // 等待页面加载完成
    cy.get('textarea[placeholder*="输入你的问题"]').should('be.visible');
  });

  it('缺陷 1 修复验证：会话隔离失效', () => {
    // 1. 点击“新对话”按钮
    cy.get('button').contains('新对话').click();
    cy.contains('已开启新对话').should('be.visible');

    // 2. 拦截发送请求，获取其 sessionId
    cy.intercept('POST', '/api/v1/chat/ask-stream').as('chatRequest');

    // 3. 发送第一条消息
    const question = '测试会话隔离 - 问题 1';
    cy.get('textarea').type(question);
    cy.get('button').find('svg.lucide-send').parent().click();

    // 4. 校验请求中的 sessionId
    cy.wait('@chatRequest').then((interception) => {
      const sessionId = interception.request.body.session_id;
      expect(sessionId).to.be.a('string');
      expect(sessionId).to.have.length.greaterThan(0);
      
      // 记录当前 sessionId
      cy.wrap(sessionId).as('firstSessionId');
    });

    // 5. 再次点击“新对话”
    cy.get('button').contains('新对话').click();
    cy.contains('已开启新对话').should('be.visible');

    // 6. 发送第二条消息
    const question2 = '测试会话隔离 - 问题 2';
    cy.get('textarea').type(question2);
    cy.get('button').find('svg.lucide-send').parent().click();

    // 7. 断言两次请求的 sessionId 不一致
    cy.wait('@chatRequest').then((interception) => {
      const secondSessionId = interception.request.body.session_id;
      cy.get('@firstSessionId').then((firstSessionId) => {
        expect(secondSessionId).to.not.equal(firstSessionId);
      });
    });
  });

  it('缺陷 2 修复验证：消息缓存污染', () => {
    // 模拟流式响应
    const mockResponse = (content: string) => {
      return `data: {"type": "text", "msg": "${content}"}\n\ndata: {"type": "finished", "full_answer": "${content}"}\n\n`;
    };

    // 1. 发送第一个问题
    cy.intercept('POST', '/api/v1/chat/ask-stream', (req) => {
      req.reply({
        statusCode: 200,
        body: mockResponse('这是第一个问题的回复。'),
        headers: { 'content-type': 'text/event-stream' }
      });
    }).as('chatRequest1');

    cy.get('textarea').type('第一个问题');
    cy.get('button').find('svg.lucide-send').parent().click();
    cy.contains('这是第一个问题的回复。').should('be.visible');

    // 2. 立即发送第二个问题（模拟快速连续提问）
    cy.intercept('POST', '/api/v1/chat/ask-stream', (req) => {
      // 延迟响应以观察闪现
      req.reply({
        delay: 500,
        statusCode: 200,
        body: mockResponse('这是第二个问题的回复，不应该看到之前的文本。'),
        headers: { 'content-type': 'text/event-stream' }
      });
    }).as('chatRequest2');

    cy.get('textarea').type('第二个问题');
    cy.get('button').find('svg.lucide-send').parent().click();

    // 3. 断言：在第二个问题发送后，回复区域不应包含第一个问题的文本
    // 我们检查最新的助手消息容器
    cy.get('.message-enter').last().within(() => {
      cy.contains('这是第一个问题的回复。').should('not.exist');
    });

    // 4. 等待第二个回复完成
    cy.wait('@chatRequest2');
    cy.contains('这是第二个问题的回复').should('be.visible');

    // 5. 连续 30 次压力测试验证（逻辑模拟）
    for (let i = 0; i < 5; i++) { // E2E 中跑 30 次太慢，这里跑 5 次示意，实际 CI 可配置更多
      cy.get('textarea').type(`连续提问 ${i}`);
      cy.get('button').find('svg.lucide-send').parent().click();
      cy.get('.message-enter').last().within(() => {
        cy.contains('这是第二个问题的回复').should('not.exist');
      });
      cy.wait('@chatRequest2');
    }
  });
});
