describe('文档预览功能测试', () => {
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
  });

  it('预览 Markdown 文件应成功加载内容', () => {
    const docId = 101;
    cy.intercept('GET', '/api/v1/documents?*', {
      statusCode: 200,
      body: {
        items: [
          {
            id: docId,
            file_name: 'test.md',
            file_extension: 'md',
            file_size: 1024,
            status: 'completed',
            created_at: new Date().toISOString(),
            mime_type: 'text/markdown'
          }
        ],
        total: 1
      }
    });

    cy.intercept('GET', `/api/v1/documents/${docId}/preview`, {
      statusCode: 200,
      body: '# Test Markdown Content\n\nThis is a test.',
      headers: { 'content-type': 'text/markdown' }
    }).as('previewText');

    cy.visit('/knowledge/1');
    cy.get(`button[title="预览"]`).first().click();
    
    cy.wait('@previewText');
    cy.contains('Test Markdown Content').should('be.visible');
  });

  it('预览 Word 文件应显示加载中并尝试渲染', () => {
    const docId = 102;
    cy.intercept('GET', '/api/v1/documents?*', {
      statusCode: 200,
      body: {
        items: [
          {
            id: docId,
            file_name: 'test.docx',
            file_extension: 'docx',
            file_size: 2048,
            status: 'completed',
            created_at: new Date().toISOString(),
            mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
          }
        ],
        total: 1
      }
    });

    // 模拟返回二进制文件
    cy.intercept('GET', `/api/v1/documents/${docId}/preview`, {
      statusCode: 200,
      body: new ArrayBuffer(0),
      headers: { 'content-type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }
    }).as('previewDocx');

    cy.visit('/knowledge/1');
    cy.get(`button[title="预览"]`).first().click();
    
    cy.contains('正在解析 Word 文档...').should('be.visible');
  });

  it('预览 Excel 文件应成功解析并显示表格', () => {
    const docId = 103;
    cy.intercept('GET', '/api/v1/documents?*', {
      statusCode: 200,
      body: {
        items: [
          {
            id: docId,
            file_name: 'test.xlsx',
            file_extension: 'xlsx',
            file_size: 3072,
            status: 'completed',
            created_at: new Date().toISOString(),
            mime_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
          }
        ],
        total: 1
      }
    });

    cy.visit('/knowledge/1');
    cy.get(`button[title="预览"]`).first().click();
    
    cy.contains('正在解析 Excel 表格...').should('be.visible');
  });

  it('预览 PPTX 文件应显示暂不支持并提供下载', () => {
    const docId = 104;
    cy.intercept('GET', '/api/v1/documents?*', {
      statusCode: 200,
      body: {
        items: [
          {
            id: docId,
            file_name: 'test.pptx',
            file_extension: 'pptx',
            file_size: 4096,
            status: 'completed',
            created_at: new Date().toISOString(),
            mime_type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
          }
        ],
        total: 1
      }
    });

    cy.visit('/knowledge/1');
    cy.get(`button[title="预览"]`).first().click();
    
    cy.contains('PPTX 格式暂不支持直接在线预览').should('be.visible');
    cy.contains('下载文档').should('be.visible');
  });
});
