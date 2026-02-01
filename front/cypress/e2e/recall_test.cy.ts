describe('召回测试页面 E2E 测试', () => {
  beforeEach(() => {
    // 登录
    cy.visit('/auth/login');
    cy.get('input[name="username"]').type('admin_rag');
    cy.get('input[name="password"]').type('admin123');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/chat');
    
    // 跳转到召回测试页面
    cy.visit('/recall/test');
  });

  it('应该能够完成完整的导入-运行-导出流程', () => {
    // 1. 检查页面元素
    cy.contains('h1', '召回测试').should('be.visible');
    cy.get('textarea[placeholder*="每行输入一条提问词"]').should('be.visible');

    // 2. 导入提问词 (模拟文本输入)
    const queries = '什么是RAG?\n如何优化检索效果?\nMilvus和ES的区别';
    cy.get('textarea').type(queries);
    cy.get('span').contains('23 / 20,000').should('be.visible');

    // 3. 配置测试
    // 选择第一个知识库 (如果存在)
    cy.get('button').contains('测试知识库').click();
    cy.get('input[type="number"]').first().clear().type('5'); // Top-N

    // 4. 运行测试
    cy.intercept('POST', '/api/v1/recall/test').as('startTest');
    cy.intercept('GET', '/api/v1/recall/status/*').as('getStatus');
    
    cy.get('button').contains('运行测试').click();
    
    cy.wait('@startTest').then((interception) => {
      expect(interception.response.statusCode).to.equal(200);
      const taskId = interception.response.body.taskId;
      expect(taskId).to.be.a('string');
    });

    // 5. 等待进度条和结果
    cy.contains('测试中').should('be.visible');
    cy.wait('@getStatus', { timeout: 30000 }).its('response.body.status').should('be.oneOf', ['running', 'finished']);
    
    // 等待测试完成
    cy.contains('测试完成', { timeout: 60000 }).should('be.visible');

    // 6. 检查结果表格
    cy.get('table').should('be.visible');
    cy.get('tbody tr').should('have.length.at.least', 1);
    cy.contains('什么是RAG?').should('be.visible');

    // 7. 导出 CSV
    cy.get('button').contains('导出 CSV').click();
    // 验证下载通常需要额外的插件，这里检查按钮是否可用
    cy.get('button').contains('导出 CSV').should('not.be.disabled');

    // 8. 详情弹窗
    cy.get('button').find('svg.lucide-external-link').first().click();
    cy.contains('测试详情').should('be.visible');
    cy.contains('召回结果').should('be.visible');
    cy.get('button').contains('关闭').click();
  });

  it('应该验证输入限制', () => {
    // 验证空输入报错
    cy.get('button').contains('运行测试').click();
    cy.contains('请输入提问词').should('be.visible');

    // 验证字符上限
    const longText = 'a'.repeat(20001);
    cy.get('textarea').invoke('val', longText).trigger('input');
    cy.contains('20,000 / 20,000').should('be.visible');
  });
});
