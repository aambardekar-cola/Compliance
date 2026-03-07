import Sidebar from './Sidebar';
import Header from './Header';

export default function Layout({ children }) {
    return (
        <div className="app-layout">
            <Sidebar />
            <Header />
            <main className="main-content">{children}</main>
        </div>
    );
}
