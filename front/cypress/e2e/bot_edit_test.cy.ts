describe('机器人编辑与测试页面 E2E 测试', () => {
  beforeEach(() => {
    // 登录
    cy.visit('/auth/login');
    cy.get('input[name="username"]').type('admin_rag');
    cy.get('input[name="password"]').type('admin123');
    cy.get('button[type="submit"]').click();
    
    // 跳转到机器人列表
    cy.visit('/robots');
    // 点击第一个机器人的“编辑并测试”链接
    cy.get('a[title="编辑并测试"]').first().click();
  });

  it('应该能够修改欢迎语并保存成功', () => {
    const newWelcome = '你好！我是重构后的助手，很高兴为你服务。' + Date.now();
    
    // 1. 修改欢迎语
    cy.get('textarea[placeholder*="开场白"]').clear().type(newWelcome);
    
    // 2. 断言保存按钮可用
    cy.get('button').contains('保存修改').should('not.be.disabled');
    
    // 3. 点击保存
    cy.intercept('PUT', '/api/v1/robots/*').as('updateRobot');
    cy.get('button').contains('保存修改').click();
    
    // 4. 等待保存完成
    cy.wait('@updateRobot').its('response.statusCode').should('equal', 200);
    cy.contains('保存成功').should('be.visible');
    
    // 5. 刷新页面验证状态不丢失
    cy.reload();
    cy.get('textarea[placeholder*="开场白"]').should('have.value', newWelcome);
  });

  it('应该能够执行召回测试并看到结果', () => {
    const query = '什么是RAG?';
    
    // 1. 输入测试问句
    cy.get('input[placeholder*="输入测试问句"]').type(query);
    
    // 2. 点击执行测试
    cy.intercept('POST', '/api/v1/robots/*/retrieval-test').as('recallTest');
    cy.get('button').contains('执行测试').click();
    
    // 3. 断言结果非空
    cy.wait('@recallTest').then((interception) => {
      expect(interception.response.statusCode).to.equal(200);
      expect(interception.response.body.results).to.have.length.at.least(1);
    });
    
    // 4. 检查 UI 显示
    cy.contains('#1').should('be.visible');
    cy.contains('Score:').should('be.visible');
  });

  it('离开页面时若有未保存变更应弹出提示', () => {
    // 1. 修改内容产生脏数据
    cy.get('input[label="机器人名称"]').type(' (Modified)');
    
    // 2. 点击返回列表
    cy.get('button').contains('返回列表').click();
    
    // 3. 验证 confirm 弹出 (Cypress 自动处理 confirm，我们可以断言它被调用)
    cy.on('window:confirm', (str) => {
      expect(str).to.equal('有未保存内容，确定离开？');
      return false; // 取消离开
    });
    
    // 4. 断言仍留在当前页
    cy.url().should('include', '/edit-test');
  });
});
