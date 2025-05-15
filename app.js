// Required dependencies
const express = require('express');
const session = require('express-session');
const path = require('path');
const { Sequelize, DataTypes } = require('sequelize');
const bcrypt = require('bcrypt');
const { OpenAI } = require('openai');
const multer = require('multer');
const fs = require('fs');
const bodyParser = require('body-parser');
const flash = require('connect-flash');
const cookieParser = require('cookie-parser');

// Initialize Express app
const app = express();

// Configure OpenAI client
const openai = new OpenAI({
  apiKey: "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"
});

// Set up middleware
app.use(express.static(path.join(__dirname, 'public')));
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(cookieParser());
app.use(flash());

// Set up session
app.use(session({
  secret: "randomSecretKey", // Equivalent to Flask's SECRET_KEY
  resave: false,
  saveUninitialized: true,
  cookie: {
    secure: process.env.NODE_ENV === 'production', // Only use secure cookies in production
    maxAge: 31 * 24 * 60 * 60 * 1000 // 31 days in milliseconds
  }
}));

// Set up database
const sequelize = new Sequelize({
  dialect: 'sqlite',
  storage: 'db.sqlite',
  logging: false
});

// Define models (equivalent to Flask SQLAlchemy models)
const VectorStore = sequelize.define('VectorStore', {
  id: {
    type: DataTypes.STRING,
    primaryKey: true
  },
  name: {
    type: DataTypes.STRING
  }
});

const Assistant = sequelize.define('Assistant', {
  id: {
    type: DataTypes.STRING,
    primaryKey: true
  },
  name: {
    type: DataTypes.STRING
  },
  instructions: {
    type: DataTypes.TEXT
  },
  tools: {
    type: DataTypes.STRING
  },
  vector_store_id: {
    type: DataTypes.STRING,
    references: {
      model: VectorStore,
      key: 'id'
    },
    allowNull: true
  },
  is_active: {
    type: DataTypes.BOOLEAN,
    defaultValue: false
  },
  interface_type: {
    type: DataTypes.STRING,
    defaultValue: "chat"
  }
});

const User = sequelize.define('User', {
  id: {
    type: DataTypes.INTEGER,
    primaryKey: true,
    autoIncrement: true
  },
  username: {
    type: DataTypes.STRING(80),
    unique: true,
    allowNull: false
  },
  email: {
    type: DataTypes.STRING(120),
    unique: true,
    allowNull: false
  },
  password: {
    type: DataTypes.STRING(200),
    allowNull: false
  },
  is_admin: {
    type: DataTypes.BOOLEAN,
    defaultValue: false
  }
});

const Thread = sequelize.define('Thread', {
  id: {
    type: DataTypes.STRING,
    primaryKey: true
  },
  session_id: {
    type: DataTypes.STRING
  },
  user_id: {
    type: DataTypes.INTEGER,
    references: {
      model: User,
      key: 'id'
    },
    allowNull: true
  }
});

const Message = sequelize.define('Message', {
  id: {
    type: DataTypes.STRING,
    primaryKey: true
  },
  thread_id: {
    type: DataTypes.STRING,
    references: {
      model: Thread,
      key: 'id'
    }
  },
  content: {
    type: DataTypes.TEXT
  },
  role: {
    type: DataTypes.STRING
  }
});

// Initialize database
async function initDb() {
  try {
    await sequelize.sync();
    console.log('Database synchronized');
  } catch (error) {
    console.error('Error synchronizing database:', error);
  }
}

// Helper functions for authentication
function isAuthenticated(req, res, next) {
  if (req.session.userId) {
    return next();
  }
  res.redirect('/login');
}

async function isAdmin(req, res, next) {
  if (!req.session.userId) {
    return res.redirect('/login');
  }

  try {
    const user = await User.findByPk(req.session.userId);
    if (user && user.is_admin) {
      return next();
    } else {
      return res.redirect('/login');
    }
  } catch (error) {
    console.error('Error checking admin status:', error);
    return res.redirect('/login');
  }
}

// Serve HTML files
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'index.html'));
});

app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'login.html'));
});

app.get('/register', (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'register.html'));
});

app.get('/admin', isAdmin, (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'admin.html'));
});

app.get('/admin/vector_stores', isAdmin, (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'vector_stores.html'));
});

app.get('/admin/vector_stores/edit/:id', isAdmin, (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'edit_vector_store.html'));
});

app.get('/admin/vector_stores/files/:vector_store_id', isAdmin, (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'vector_store_files.html'));
});

app.get('/admin/assistants', isAdmin, (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'assistants.html'));
});

app.get('/chat/:thread_id?', (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'chat.html'));
});

app.get('/profile', isAuthenticated, (req, res) => {
  res.sendFile(path.join(__dirname, 'views', 'profile.html'));
});

// Login route
app.post('/login', async (req, res) => {
  const { username, password, remember } = req.body;

  try {
    const user = await User.findOne({ where: { username } });
    if (user && await bcrypt.compare(password, user.password)) {
      req.session.userId = user.id;
      if (remember) {
        req.session.cookie.maxAge = 31 * 24 * 60 * 60 * 1000; // 31 days
      } else {
        req.session.cookie.expires = false;
      }
      return res.redirect(user.is_admin ? '/admin' : '/chat');
    }

    return res.redirect('/login');
  } catch (error) {
    console.error('Login error:', error);
    return res.redirect('/login');
  }
});

// Register route
app.post('/register', async (req, res) => {
  const { username, email, password } = req.body;

  try {
    const existingUser = await User.findOne({ where: { username } });
    if (existingUser) {
      return res.send('Username already exists');
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const user = await User.create({
      username,
      email,
      password: hashedPassword
    });

    req.session.userId = user.id;
    return res.redirect('/chat');
  } catch (error) {
    console.error('Registration error:', error);
    return res.send('An error occurred during registration');
  }
});

// Logout route
app.get('/logout', isAuthenticated, (req, res) => {
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

// Profile route
app.post('/profile', isAuthenticated, async (req, res) => {
  const { username, email, password } = req.body;

  try {
    const user = await User.findByPk(req.session.userId);
    user.username = username;
    user.email = email;

    if (password) {
      user.password = await bcrypt.hash(password, 10);
    }

    await user.save();
    res.redirect('/profile');
  } catch (error) {
    console.error('Error updating profile:', error);
    res.redirect('/profile');
  }
});

// Admin - Select assistant
app.post('/select_assistant', isAdmin, async (req, res) => {
  const { assistant_id, interface_type } = req.body;

  try {
    // Deactivate all assistants with the given interface type
    await Assistant.update(
      { is_active: false },
      { where: { interface_type } }
    );

    // Activate the selected assistant
    const assistant = await Assistant.findByPk(assistant_id);
    if (assistant) {
      assistant.is_active = true;
      assistant.interface_type = interface_type;
      await assistant.save();
    }

    res.redirect('/admin');
  } catch (error) {
    console.error('Error selecting assistant:', error);
    res.redirect('/admin');
  }
});

// Vector stores routes
app.post('/admin/vector_stores/create', isAdmin, async (req, res) => {
  const { name } = req.body;

  try {
    const vectorStore = await openai.vectorStores.create({
      name
    });

    await VectorStore.create({
      id: vectorStore.id,
      name
    });

    res.redirect('/admin/vector_stores');
  } catch (error) {
    console.error('Error creating vector store:', error);
    res.redirect('/admin/vector_stores');
  }
});

app.post('/admin/vector_stores/delete/:id', isAdmin, async (req, res) => {
  const { id } = req.params;

  try {
    await openai.vectorStores.del(id);
    await VectorStore.destroy({ where: { id } });
    res.redirect('/admin/vector_stores');
  } catch (error) {
    console.error('Error deleting vector store:', error);
    res.redirect('/admin/vector_stores');
  }
});

app.post('/admin/vector_stores/update/:id', isAdmin, async (req, res) => {
  const { id } = req.params;
  const { name } = req.body;

  try {
    await openai.vectorStores.update(id, { name });
    const vectorStore = await VectorStore.findByPk(id);
    vectorStore.name = name;
    await vectorStore.save();
    res.redirect('/admin/vector_stores');
  } catch (error) {
    console.error('Error updating vector store:', error);
    res.redirect('/admin/vector_stores');
  }
});

// Setup multer for file uploads
const upload = multer({ dest: 'uploads/' });

app.post('/admin/vector_stores/:vector_store_id/upload_file', isAdmin, upload.array('file'), async (req, res) => {
  const { vector_store_id } = req.params;
  const ALLOWED_EXTENSIONS = [
    'c', 'cpp', 'cs', 'css', 'doc', 'docx', 'go', 'html',
    'java', 'js', 'json', 'md', 'pdf', 'php', 'pptx',
    'py', 'rb', 'sh', 'tex', 'ts', 'txt'
  ];

  function allowedFile(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    return ALLOWED_EXTENSIONS.includes(ext);
  }

  try {
    const uploadedFiles = [];

    for (const file of req.files) {
      if (file && allowedFile(file.originalname)) {
        try {
          // Upload to OpenAI
          const openaiFile = await openai.files.create({
            file: fs.createReadStream(file.path),
            purpose: "assistants"
          });

          // Add to vector store
          await openai.vectorStores.files.create(
            vector_store_id,
            { file_id: openaiFile.id }
          );

          uploadedFiles.push(file.originalname);
        } catch (error) {
          console.error(`Error uploading file ${file.originalname}: ${error.message}`);
        } finally {
          // Clean up temp file
          if (fs.existsSync(file.path)) {
            fs.unlinkSync(file.path);
          }
        }
      } else {
        console.error(`Invalid file type: ${file.originalname}`);
        // Clean up temp file
        if (file && file.path && fs.existsSync(file.path)) {
          fs.unlinkSync(file.path);
        }
      }
    }

    res.redirect(`/admin/vector_stores/files/${vector_store_id}`);
  } catch (error) {
    console.error('Error uploading files:', error);
    res.redirect(`/admin/vector_stores/files/${vector_store_id}`);
  }
});

app.post('/admin/vector_stores/:vector_store_id/delete_file/:file_id', isAdmin, async (req, res) => {
  const { vector_store_id, file_id } = req.params;

  try {
    await openai.vectorStores.files.del(vector_store_id, file_id);
    res.redirect(`/admin/vector_stores/files/${vector_store_id}`);
  } catch (error) {
    console.error('Error deleting file from vector store:', error);
    res.redirect(`/admin/vector_stores/files/${vector_store_id}`);
  }
});

// Assistants routes
app.post('/admin/assistants/create', isAdmin, async (req, res) => {
  const { name, instructions, tools: toolsList, vector_store_id, interface_type } = req.body;
  let tools = Array.isArray(toolsList) ? toolsList : [toolsList].filter(Boolean);

  try {
    // Format tools for OpenAI API
    const formattedTools = tools.map(tool => {
      if (tool === "file_search") {
        return { type: "file_search" };
      } else if (tool === "code_interpreter") {
        return { type: "code_interpreter" };
      }
    }).filter(Boolean);

    // Setup tool resources if file_search is selected
    let toolResources = {};
    if (tools.includes("file_search") && vector_store_id) {
      toolResources = { file_search: { vector_store_ids: [vector_store_id] } };
    }

    // Create assistant with OpenAI
    const assistant = await openai.beta.assistants.create({
      name,
      instructions,
      tools: formattedTools,
      model: "gpt-4o-mini",
      tool_resources: toolResources
    });

    // Check if this should be the active assistant for the interface type
    const isActive = !await Assistant.findOne({
      where: {
        interface_type,
        is_active: true
      }
    });

    // Save to database
    await Assistant.create({
      id: assistant.id,
      name,
      instructions,
      tools: JSON.stringify(tools),
      vector_store_id,
      interface_type: interface_type || "chat",
      is_active: isActive
    });

    res.redirect('/admin/assistants');
  } catch (error) {
    console.error('Error creating assistant:', error);
    res.redirect('/admin/assistants');
  }
});

app.post('/admin/assistants/delete/:id', isAdmin, async (req, res) => {
  const { id } = req.params;

  try {
    await openai.beta.assistants.del(id);
    await Assistant.destroy({ where: { id } });
    res.redirect('/admin/assistants');
  } catch (error) {
    console.error('Error deleting assistant:', error);
    res.redirect('/admin/assistants');
  }
});

// API endpoints for frontend data
app.get('/api/admin/assistants', isAdmin, async (req, res) => {
  try {
    const assistants = await Assistant.findAll();
    res.json(assistants);
  } catch (error) {
    console.error('Error fetching assistants:', error);
    res.status(500).json({ error: 'Failed to fetch assistants' });
  }
});

app.get('/api/admin/vector_stores', isAdmin, async (req, res) => {
  try {
    const vectorStores = await VectorStore.findAll();
    res.json(vectorStores);
  } catch (error) {
    console.error('Error fetching vector stores:', error);
    res.status(500).json({ error: 'Failed to fetch vector stores' });
  }
});

app.get('/api/admin/vector_stores/:id', isAdmin, async (req, res) => {
  try {
    const vectorStore = await VectorStore.findByPk(req.params.id);
    if (!vectorStore) {
      return res.status(404).json({ error: 'Vector store not found' });
    }
    res.json(vectorStore);
  } catch (error) {
    console.error('Error fetching vector store:', error);
    res.status(500).json({ error: 'Failed to fetch vector store' });
  }
});

app.get('/api/admin/vector_stores/files/:vector_store_id', isAdmin, async (req, res) => {
  const { vector_store_id } = req.params;
  const page = parseInt(req.query.page) || 1;
  const limit = 10; // Files per page

  try {
    let allFiles = [];
    let hasMore = true;
    let after = null;

    while (hasMore) {
      const options = { vector_store_id, limit: limit + 1 };
      if (after) {
        options.after = after;
      }

      const files = await openai.vectorStores.files.list(options);

      // Add filename to each file
      for (const file of files.data) {
        try {
          const fileInfo = await openai.files.retrieve(file.id);
          file.filename = fileInfo.filename;
        } catch (e) {
          file.filename = `Unknown filename (ID: ${file.id})`;
          console.error(`Error retrieving file info: ${e.message}`);
        }
      }

      allFiles.push(...files.data);

      if (files.has_more) {
        after = files.last_id;
      } else {
        hasMore = false;
      }
    }

    // Calculate pagination
    const offset = (page - 1) * limit;
    const paginatedFiles = allFiles.slice(offset, offset + limit);
    const totalFiles = allFiles.length;
    const totalPages = Math.ceil(totalFiles / limit);

    res.json({
      files: paginatedFiles,
      pagination: {
        page,
        totalPages,
        totalFiles
      }
    });
  } catch (error) {
    console.error('Error fetching vector store files:', error);
    res.status(500).json({ error: 'Failed to fetch vector store files' });
  }
});

// Chat functionality
app.post('/chat', async (req, res) => {
  const { message } = req.body;
  const threadId = req.body.thread_id || req.session.threadId;

  try {
    // Find active chat assistant
    const activeAssistant = await Assistant.findOne({
      where: {
        is_active: true,
        interface_type: "chat"
      }
    });

    if (!activeAssistant) {
      return res.status(500).json({ error: "No active assistant found for chat interface" });
    }

    let currentThreadId = threadId;

    // Create new thread if needed
    if (!currentThreadId) {
      const thread = await openai.beta.threads.create();
      currentThreadId = thread.id;
      req.session.threadId = currentThreadId;

      // Save thread to database
      await Thread.create({
        id: currentThreadId,
        user_id: req.session.userId || null
      });
    }

    // Add user message to thread
    const userMessage = await openai.beta.threads.messages.create(
      currentThreadId,
      {
        role: "user",
        content: message
      }
    );

    // Save message to database
    await Message.create({
      id: userMessage.id,
      thread_id: currentThreadId,
      content: message,
      role: "user"
    });

    // Create run
    const run = await openai.beta.threads.runs.create(
      currentThreadId,
      {
        assistant_id: activeAssistant.id
      }
    );

    // Poll for completion
    let completed = false;
    let maxRetries = 60; // 60 seconds timeout
    let assistantResponse;

    while (!completed && maxRetries > 0) {
      const runStatus = await openai.beta.threads.runs.retrieve(
        currentThreadId,
        run.id
      );

      if (runStatus.status === "completed") {
        completed = true;
      } else if (runStatus.status === "failed") {
        return res.status(500).json({ error: "Assistant response failed" });
      } else {
        // Wait 1 second before checking again
        await new Promise(resolve => setTimeout(resolve, 1000));
        maxRetries--;
      }
    }

    if (!completed) {
      return res.status(500).json({ error: "Timeout waiting for assistant response" });
    }

    // Get latest message (assistant's response)
    const messages = await openai.beta.threads.messages.list(
      currentThreadId,
      {
        order: "desc",
        limit: 1
      }
    );

    if (!messages.data.length) {
      return res.status(500).json({ error: "No response from assistant" });
    }

    assistantResponse = messages.data[0].content[0].text.value;

    // Save assistant message to database
    await Message.create({
      id: messages.data[0].id,
      thread_id: currentThreadId,
      content: assistantResponse,
      role: "assistant"
    });

    return res.json({
      messages: [
        { role: "user", content: message },
        { role: "assistant", content: assistantResponse }
      ]
    });

  } catch (error) {
    console.error('Error in chat:', error);
    return res.status(500).json({ error: error.message });
  }
});

app.get('/api/chat/threads', isAuthenticated, async (req, res) => {
  try {
    const threads = await Thread.findAll({
      where: { user_id: req.session.userId },
      include: [{
        model: Message,
        limit: 1,
        order: [['id', 'ASC']]
      }]
    });

    const formattedThreads = threads.map(thread => ({
      id: thread.id,
      preview: thread.Messages && thread.Messages[0]
        ? thread.Messages[0].content.substring(0, 50)
        : "New conversation"
    }));

    res.json(formattedThreads);
  } catch (error) {
    console.error('Error fetching threads:', error);
    res.status(500).json({ error: 'Failed to fetch threads' });
  }
});

app.get('/api/chat/messages/:thread_id', async (req, res) => {
  const { thread_id } = req.params;

  try {
    const messages = await Message.findAll({
      where: { thread_id },
      order: [['id', 'ASC']]
    });

    const formattedMessages = messages.map(msg => ({
      role: msg.role,
      content: msg.content
    }));

    res.json(formattedMessages);
  } catch (error) {
    console.error('Error fetching messages:', error);
    res.status(500).json({ error: 'Failed to fetch messages' });
  }
});

// Define model relationships
User.hasMany(Thread);
Thread.belongsTo(User);
Thread.hasMany(Message);
Message.belongsTo(Thread);

// Initialize database and start server
initDb().then(() => {
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on port ${PORT}`);
  });
}).catch(err => {
  console.error('Failed to start server:', err);
});