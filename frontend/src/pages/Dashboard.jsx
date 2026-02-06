import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, BookOpen, MoreVertical, Calendar, ArrowRight, LogOut, Upload, FileText, Loader2, X, Trash2 } from 'lucide-react';
import { createProject, uploadDocument, getProjects, deleteProject } from '../api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

const Dashboard = () => {
    const navigate = useNavigate();
    const { user, logout } = useAuth();
    const toast = useToast();
    const [showNewProjectModal, setShowNewProjectModal] = useState(false);
    const [newProjectName, setNewProjectName] = useState('');
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [isCreating, setIsCreating] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const [uploadStatus, setUploadStatus] = useState({}); // { fileName: 'pending' | 'uploading' | 'success' | 'error' }
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    // Delete Modal State
    const [deleteTargetId, setDeleteTargetId] = useState(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const fileInputRef = useRef(null);

    useEffect(() => {
        fetchProjects();
    }, []);

    const fetchProjects = async () => {
        try {
            const data = await getProjects();
            setProjects(data);
        } catch (error) {
            console.error("Failed to fetch projects:", error);
        } finally {
            setLoading(false);
        }
    };

    // ... handlers ...

    if (loading) {
        return (
            <div className="min-h-screen bg-[#FDF6F0] font-sans text-[#4A3B32]">
                <header className="bg-white border-b border-[#E6D5CC] sticky top-0 z-10">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
                        <div className="skeleton h-10 w-40"></div>
                        <div className="skeleton h-10 w-10 full-rounded"></div>
                    </div>
                </header>
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
                    <div className="mb-12">
                        <div className="skeleton h-8 w-48 mb-2"></div>
                        <div className="skeleton h-4 w-64"></div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="h-48 bg-white rounded-2xl border border-[#E6D5CC] p-6">
                                <div className="skeleton h-12 w-12 rounded-xl mb-6"></div>
                                <div className="skeleton h-6 w-3/4 mb-4"></div>
                                <div className="skeleton h-4 w-1/2"></div>
                            </div>
                        ))}
                    </div>
                </main>
            </div>
        );
    }

    const confirmDeleteProject = async () => {
        if (!deleteTargetId) return;
        setIsDeleting(true);
        try {
            await deleteProject(deleteTargetId);
            setProjects(prev => prev.filter(p => p.id !== deleteTargetId));
            setDeleteTargetId(null);
        } catch (error) {
            console.error("Failed to delete project:", error);
            toast.error('Failed to delete project');
        } finally {
            setIsDeleting(false);
        }
    };

    const handleDeleteClick = (e, projectId) => {
        e.stopPropagation();
        setDeleteTargetId(projectId);
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        if (!newProjectName.trim() || selectedFiles.length === 0) return;

        setIsCreating(true);

        // Initialize status
        const initialStatus = {};
        selectedFiles.forEach(f => initialStatus[f.name] = 'pending');
        setUploadStatus(initialStatus);

        try {
            // 1. Create Project
            const projectData = await createProject(newProjectName);

            if (projectData && projectData.id) {
                // 2. Upload Documents Sequentially
                for (const file of selectedFiles) {
                    setUploadStatus(prev => ({ ...prev, [file.name]: 'uploading' }));
                    try {
                        await uploadDocument(projectData.id, file);
                        setUploadStatus(prev => ({ ...prev, [file.name]: 'success' }));
                    } catch (err) {
                        console.error(`Failed to upload ${file.name}`, err);
                        setUploadStatus(prev => ({ ...prev, [file.name]: 'error' }));
                    }
                }

                // Delay redirect
                setTimeout(() => {
                    navigate(`/project/${projectData.id}`);
                }, 1000);
            }
        } catch (error) {
            console.error("Error creating project:", error);
            toast.error('Failed to create project. Please try again.');
            setIsCreating(false);
        }
    };

    const handleFileSelect = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setSelectedFiles(prev => [...prev, ...Array.from(e.target.files)]);
        }
    };

    const removeFile = (index) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    // Drag and Drop Handlers
    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            // Filter for accepted types
            const files = Array.from(e.dataTransfer.files).filter(file =>
                /\.(pdf|txt|docx)$/i.test(file.name)
            );
            setSelectedFiles(prev => [...prev, ...files]);
        }
    };

    return (
        <div className="min-h-screen bg-[#FDF6F0] font-sans text-[#4A3B32]">
            {/* Header */}
            <header className="bg-white border-b border-[#E6D5CC] sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 bg-[#C8A288] rounded-xl flex items-center justify-center text-white shadow-md shadow-[#C8A288]/20">
                            <BookOpen className="h-6 w-6" />
                        </div>
                        <h1 className="text-2xl font-bold text-[#4A3B32]">Lumina IQ</h1>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-[#FDF6F0] rounded-full border border-[#E6D5CC]">
                            <div className="h-8 w-8 bg-[#C8A288] rounded-full flex items-center justify-center text-white text-sm font-bold">
                                {user?.full_name ? user.full_name.charAt(0).toUpperCase() : user?.email?.charAt(0).toUpperCase()}
                            </div>
                            <span className="font-medium text-sm">{user?.full_name || user?.email}</span>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="p-2 text-[#8a6a5c] hover:bg-[#FDF6F0] rounded-full transition-colors"
                        >
                            <LogOut className="h-5 w-5" />
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
                    <div>
                        <h2 className="text-3xl font-bold mb-2">Your Projects</h2>
                        <p className="text-[#8a6a5c]">Manage and organize your learning materials</p>
                    </div>

                    <div className="flex flex-col md:flex-row gap-4 w-full md:w-auto">
                        <div className="relative w-full md:w-auto">
                            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-[#8a6a5c]" />
                            <input
                                type="text"
                                placeholder="Search projects..."
                                className="pl-12 pr-4 py-3 bg-white border border-[#E6D5CC] rounded-xl focus:ring-2 focus:ring-[#C8A288] outline-none w-full md:w-64"
                            />
                        </div>
                        <button
                            onClick={() => setShowNewProjectModal(true)}
                            className="px-6 py-3 bg-[#C8A288] text-white rounded-xl font-medium hover:bg-[#B08B72] transition-colors flex items-center justify-center gap-2 shadow-lg shadow-[#C8A288]/20 w-full md:w-auto"
                        >
                            <Plus className="h-5 w-5" />
                            <span>New Project</span>
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {projects.map((project) => (
                        <div
                            key={project.id}
                            onClick={() => navigate(`/project/${project.id}`)}
                            className="group bg-white p-6 rounded-2xl border border-[#E6D5CC] hover:border-[#C8A288] hover:shadow-lg hover:shadow-[#C8A288]/10 transition-all cursor-pointer relative overflow-hidden"
                        >
                            <div className="absolute top-0 right-0 p-6 opacity-0 group-hover:opacity-100 transition-opacity">
                                <ArrowRight className="h-5 w-5 text-[#C8A288]" />
                            </div>

                            <button
                                onClick={(e) => handleDeleteClick(e, project.id)}
                                className="absolute top-4 right-4 p-2 text-[#8a6a5c] hover:text-red-600 hover:bg-red-50 rounded-full transition-colors z-20 opacity-100"
                                title="Delete Project"
                            >
                                <Trash2 className="h-5 w-5" />
                            </button>

                            <div className="h-12 w-12 bg-[#FDF6F0] rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                                <BookOpen className="h-6 w-6 text-[#C8A288]" />
                            </div>

                            <h3 className="text-xl font-bold mb-2 group-hover:text-[#C8A288] transition-colors">{project.name}</h3>

                            <div className="flex items-center gap-4 text-sm text-[#8a6a5c] mt-4 pt-4 border-t border-[#FDF6F0]">
                                <div className="flex items-center gap-1.5">
                                    <Calendar className="h-4 w-4" />
                                    <span>{new Date(project.created_at).toLocaleDateString()}</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <BookOpen className="h-4 w-4" />
                                    <span>{project.docs || 0} Docs</span>
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* New Project Card Placeholder */}
                    <button
                        onClick={() => setShowNewProjectModal(true)}
                        className="flex flex-col items-center justify-center p-6 rounded-2xl border-2 border-dashed border-[#E6D5CC] hover:border-[#C8A288] hover:bg-[#FDF6F0]/50 transition-all group h-full min-h-[200px]"
                    >
                        <div className="h-12 w-12 bg-[#FDF6F0] rounded-full flex items-center justify-center mb-4 group-hover:bg-[#C8A288] transition-colors">
                            <Plus className="h-6 w-6 text-[#C8A288] group-hover:text-white transition-colors" />
                        </div>
                        <span className="font-medium text-[#8a6a5c] group-hover:text-[#C8A288]">Create New Project</span>
                    </button>
                </div>
            </main>

            {/* New Project Modal */}
            {showNewProjectModal && (
                <div className="fixed inset-0 bg-[#4A3B32]/20 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl animate-in fade-in zoom-in duration-200">
                        <h3 className="text-2xl font-bold mb-2">Create New Project</h3>
                        <p className="text-[#8a6a5c] mb-6">Start by naming your project and uploading documents.</p>

                        <form onSubmit={handleCreateProject}>
                            {!isCreating ? (
                                <>
                                    <div className="mb-4">
                                        <label className="block text-sm font-medium mb-1 text-[#4A3B32]">Project Name</label>
                                        <input
                                            type="text"
                                            autoFocus
                                            value={newProjectName}
                                            onChange={(e) => setNewProjectName(e.target.value)}
                                            placeholder="e.g., Biology 101"
                                            className="w-full px-6 py-4 bg-[#FDF6F0] border border-[#E6D5CC] rounded-xl focus:ring-2 focus:ring-[#C8A288] outline-none text-lg"
                                        />
                                    </div>

                                    <div className="mb-6">
                                        <label className="block text-sm font-medium mb-1 text-[#4A3B32]">Upload Documents</label>
                                        <div
                                            onClick={() => fileInputRef.current?.click()}
                                            onDragEnter={handleDrag}
                                            onDragLeave={handleDrag}
                                            onDragOver={handleDrag}
                                            onDrop={handleDrop}
                                            className={`w-full px-6 py-8 bg-[#FDF6F0] border-2 border-dashed rounded-xl cursor-pointer transition-all flex flex-col items-center justify-center gap-2 text-[#8a6a5c] ${dragActive ? 'border-[#C8A288] bg-[#E6D5CC]/30' : 'border-[#C8A288] hover:bg-[#E6D5CC]/30'
                                                }`}
                                        >
                                            <Upload className="h-8 w-8 text-[#C8A288]" />
                                            <p className="font-medium text-[#4A3B32]">Click to upload or drag and drop</p>
                                            <p className="text-xs">PDF, TXT, DOCX (Multiple allowed)</p>

                                            <input
                                                type="file"
                                                ref={fileInputRef}
                                                className="hidden"
                                                accept=".pdf,.txt,.docx"
                                                multiple
                                                onChange={handleFileSelect}
                                            />
                                        </div>

                                        {/* Selected Files List */}
                                        {selectedFiles.length > 0 && (
                                            <div className="mt-4 space-y-2 max-h-40 overflow-y-auto">
                                                {selectedFiles.map((file, index) => (
                                                    <div key={index} className="flex items-center justify-between p-3 bg-[#FDF6F0] border border-[#E6D5CC] rounded-lg">
                                                        <div className="flex items-center gap-3 overflow-hidden">
                                                            <FileText className="h-4 w-4 text-[#C8A288] shrink-0" />
                                                            <span className="text-sm font-medium truncate">{file.name}</span>
                                                        </div>
                                                        <button
                                                            type="button"
                                                            onClick={() => removeFile(index)}
                                                            className="p-1 hover:bg-[#E6D5CC] rounded-full text-[#8a6a5c]"
                                                        >
                                                            <X className="h-4 w-4" />
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex gap-3">
                                        <button
                                            type="button"
                                            onClick={() => setShowNewProjectModal(false)}
                                            className="flex-1 py-3 px-6 rounded-xl font-medium text-[#8a6a5c] hover:bg-[#FDF6F0] transition-colors"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={!newProjectName.trim() || selectedFiles.length === 0}
                                            className="flex-1 py-3 px-6 bg-[#C8A288] text-white rounded-xl font-medium hover:bg-[#B08B72] disabled:opacity-50 transition-colors shadow-lg shadow-[#C8A288]/20 flex items-center justify-center gap-2"
                                        >
                                            <span>Create & Start</span>
                                        </button>
                                    </div>
                                </>
                            ) : (
                                <div className="space-y-4">
                                    <div className="text-center py-4">
                                        <Loader2 className="h-8 w-8 animate-spin text-[#C8A288] mx-auto mb-2" />
                                        <h4 className="font-bold text-lg">Creating Project...</h4>
                                        <p className="text-sm text-[#8a6a5c]">Please wait while we process your documents.</p>
                                    </div>

                                    <div className="max-h-60 overflow-y-auto space-y-2 border-t border-[#E6D5CC] pt-4">
                                        {selectedFiles.map((file, idx) => (
                                            <div key={idx} className="flex items-center justify-between text-sm p-2 rounded bg-[#FDF6F0]">
                                                <span className="truncate max-w-[70%]">{file.name}</span>
                                                <span className={`font-bold text-xs px-2 py-1 rounded ${uploadStatus[file.name] === 'success' ? 'bg-green-100 text-green-700' :
                                                    uploadStatus[file.name] === 'error' ? 'bg-red-100 text-red-700' :
                                                        uploadStatus[file.name] === 'uploading' ? 'bg-blue-100 text-blue-700' :
                                                            'bg-gray-100 text-gray-500'
                                                    }`}>
                                                    {uploadStatus[file.name] === 'uploading' ? 'Uploading...' :
                                                        uploadStatus[file.name] === 'success' ? 'Done' :
                                                            uploadStatus[file.name] === 'error' ? 'Failed' : 'Pending'}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </form>
                    </div>
                </div>
            )}
            {/* Delete Confirmation Modal */}
            {deleteTargetId && (
                <div className="fixed inset-0 bg-[#4A3B32]/20 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-3xl p-8 max-w-sm w-full shadow-2xl animate-in fade-in zoom-in duration-200 text-center">
                        <div className="h-16 w-16 bg-red-50 rounded-2xl flex items-center justify-center text-red-500 mx-auto mb-4">
                            <Trash2 className="h-8 w-8" />
                        </div>
                        <h3 className="text-xl font-bold mb-2 text-[#4A3B32]">Delete Project?</h3>
                        <p className="text-[#8a6a5c] mb-6 text-sm">
                            This action cannot be undone. All documents and chats associated with this project will be permanently removed.
                        </p>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setDeleteTargetId(null)}
                                disabled={isDeleting}
                                className="flex-1 py-3 px-4 rounded-xl font-medium text-[#8a6a5c] hover:bg-[#FDF6F0] transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDeleteProject}
                                disabled={isDeleting}
                                className="flex-1 py-3 px-4 bg-red-500 text-white rounded-xl font-bold hover:bg-red-600 transition-colors shadow-lg shadow-red-500/20 flex items-center justify-center gap-2"
                            >
                                {isDeleting ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        <span>Deleting...</span>
                                    </>
                                ) : (
                                    <span>Delete</span>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;