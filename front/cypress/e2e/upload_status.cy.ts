describe('上传状态管理测试', () => {
  beforeEach(() => {
    // 登录
    cy.intercept('POST', '/api/v1/auth/login', {
      statusCode: 200,
      body: {
        access_token: 'fake_token',
        token_type: 'bearer',
        user: { id: 1, username: 'admin', role: 'admin' }
      }
    });

    cy.visit('/auth/login');
    cy.get('input[name="username"]').type('admin');
    cy.get('input[name="password"]').type('Admin@123');
    cy.get('button[type="submit"]').click();

    // 模拟知识库详情
    cy.intercept('GET', '/api/v1/knowledge/1', {
      statusCode: 200,
      body: {
        id: 1,
        name: '测试知识库',
        document_count: 5,
        total_chunks: 100
      }
    });

    // 模拟初始文档列表
    cy.intercept('GET', '/api/v1/documents?*', {
      statusCode: 200,
      body: {
        items: [],
        total: 0
      }
    }).as('getDocs');
  });

  it('上传成功后应平滑更新状态，不显示全屏 Loading', () => {
    // 模拟健康检查失败（触发预检警告）
    cy.intercept('GET', '/api/v1/health/es', {
      statusCode: 503,
      body: { detail: 'ES Service Unavailable' }
    }).as('healthCheck');

    // 模拟上传成功
    cy.intercept('POST', '/api/v1/documents/upload?*', {
      statusCode: 200,
      body: {
        document_id: 123,
        filename: 'test_success.pdf',
        file_size: 1024,
        mime_type: 'application/pdf',
        preview_url: '/preview/123'
      }
    }).as('uploadFile');

    // 模拟上传后的静默刷新
    cy.intercept('GET', '/api/v1/documents?*', {
      statusCode: 200,
      body: {
        items: [
          {
            id: 123,
            file_name: 'test_success.pdf',
            file_extension: 'pdf',
            file_size: 1024,
            status: 'uploading',
            created_at: new Date().toISOString()
          }
        ],
        total: 1
      }
    }).as('getDocsAfterUpload');

    cy.visit('/knowledge/1');
    cy.wait('@getDocs');

    // 模拟文件选择并上传
    const fileName = 'test_success.pdf';
    cy.get('input[type="file"]').selectFile({
      contents: Cypress.Buffer.from('file content'),
      fileName: fileName,
      lastModified: Date.now(),
    }, { force: true });

    // 检查预检警告是否显示（应该是 loading 状态而不是 error 状态）
    cy.contains('后端分词器配置错误').should('be.visible');

    cy.wait('@uploadFile');
    cy.wait('@getDocsAfterUpload');

    // 检查成功提示
    cy.contains('成功上传 1 个文件').should('be.visible');

    // 检查全屏 Loading 不应该出现（因为是 silent refresh）
    cy.get('.page-loading-spinner').should('not.exist');

    // 检查列表已更新
    cy.contains('test_success.pdf').should('be.visible');
  });

  it('上传真正失败时应正确显示错误记录', () => {
    // 模拟健康检查成功
    cy.intercept('GET', '/api/v1/health/es', {
      statusCode: 200,
      body: { status: 'ok' }
    });

    // 模拟上传失败
    cy.intercept('POST', '/api/v1/documents/upload?*', {
      statusCode: 500,
      body: { msg: 'Internal Server Error' }
    }).as('uploadFail');

    cy.visit('/knowledge/1');
    
    const fileName = 'test_fail.pdf';
    cy.get('input[type="file"]').selectFile({
      contents: Cypress.Buffer.from('file content'),
      fileName: fileName,
      lastModified: Date.now(),
    }, { force: true });

    cy.wait('@uploadFail');

    // 检查错误提示
    cy.contains('test_fail.pdf: Internal Server Error').should('be.visible');

    // 检查列表中的错误记录
    cy.contains('test_fail.pdf').should('be.visible');
    cy.contains('上传失败').should('be.visible');
  });
});
